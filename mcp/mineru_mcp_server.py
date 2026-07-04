"""
MCP Server for MinerU Document OCR API.
Uses MinerU Agent lightweight API: https://mineru.net/api/v1/agent
"""
import asyncio
import json
import sys
import os
import time
import requests
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

MINERU_BASE_URL = "https://mineru.net/api/v1/agent"
REQUEST_TIMEOUT = 300  # seconds
POLL_INTERVAL = 3  # seconds

server = Server("mineru-ocr")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="parse_document",
            description="使用 MinerU 引擎将文档（PDF/Word/PPT/图片）解析为 Markdown 格式并保存到指定文件夹。"
            "支持 PDF、DOCX、PPTX、PNG、JPG 等格式，文件限制 10MB、20 页。"
            "适用于论文审稿、文档分析等需要精确提取文档内容的场景。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "待解析文件的绝对路径，如 E:/paper.pdf",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出文件夹的绝对路径。不传则默认保存到源文件所在目录。",
                        "default": None,
                    },
                    "language": {
                        "type": "string",
                        "description": "文档语言代码。常见值：en（英文）、ch（中文）、korean、japan、latin。默认 ch。",
                        "default": "ch",
                    },
                    "page_range": {
                        "type": "string",
                        "description": "页码范围，如 '1-10' 或 '5'。仅对 PDF 有效。",
                        "default": None,
                    },
                    "enable_table": {
                        "type": "boolean",
                        "description": "是否开启表格识别，默认 true。",
                        "default": True,
                    },
                    "is_ocr": {
                        "type": "boolean",
                        "description": "是否开启 OCR，默认 false。",
                        "default": False,
                    },
                    "enable_formula": {
                        "type": "boolean",
                        "description": "是否开启公式识别，默认 true。",
                        "default": True,
                    },
                },
                "required": ["file_path"],
            },
        )
    ]


def _get_upload_url(file_name, language, page_range, enable_table, is_ocr, enable_formula):
    """获取 MinerU 签名上传 URL"""
    data = {
        "file_name": file_name,
        "language": language,
        "enable_table": enable_table,
        "is_ocr": is_ocr,
        "enable_formula": enable_formula,
    }
    if page_range:
        data["page_range"] = page_range

    resp = requests.post(
        f"{MINERU_BASE_URL}/parse/file",
        json=data,
        timeout=30,
    )
    result = resp.json()
    if result["code"] != 0:
        raise Exception(f"获取上传链接失败: {result['msg']}")
    return result["data"]["task_id"], result["data"]["file_url"]


def _upload_file(file_path, file_url):
    """PUT 上传文件到 OSS"""
    with open(file_path, "rb") as f:
        resp = requests.put(file_url, data=f, timeout=REQUEST_TIMEOUT)
    if resp.status_code not in (200, 201):
        raise Exception(f"文件上传失败, HTTP {resp.status_code}")


def _poll_result(task_id, timeout=300):
    """轮询查询解析结果"""
    state_labels = {
        "uploading": "文件下载中",
        "pending": "排队中",
        "running": "解析中",
        "waiting-file": "等待文件上传",
    }
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{MINERU_BASE_URL}/parse/{task_id}",
            timeout=30,
        )
        result = resp.json()
        state = result["data"]["state"]
        elapsed = int(time.time() - start)

        if state == "done":
            return result["data"]["markdown_url"]
        if state == "failed":
            err_msg = result["data"].get("err_msg", "未知错误")
            raise Exception(f"解析失败: {err_msg}")

        time.sleep(POLL_INTERVAL)

    raise Exception(f"轮询超时 ({timeout}s)")


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "parse_document":
        raise ValueError(f"Unknown tool: {name}")

    file_path = arguments.get("file_path", "")
    output_dir = arguments.get("output_dir", None)
    language = arguments.get("language", "ch")
    page_range = arguments.get("page_range", None)
    enable_table = arguments.get("enable_table", True)
    is_ocr = arguments.get("is_ocr", False)
    enable_formula = arguments.get("enable_formula", True)

    if not os.path.isfile(file_path):
        return [TextContent(type="text", text=f"错误：文件不存在 — {file_path}")]

    if not output_dir:
        output_dir = os.path.dirname(os.path.abspath(file_path))

    filename = os.path.basename(file_path)

    try:
        # Step 1: 获取签名上传 URL
        task_id, file_url = _get_upload_url(
            filename, language, page_range, enable_table, is_ocr, enable_formula
        )

        # Step 2: 上传文件
        _upload_file(file_path, file_url)

        # Step 3: 轮询结果
        markdown_url = _poll_result(task_id, timeout=REQUEST_TIMEOUT)

        # Step 4: 下载 Markdown
        md_resp = requests.get(markdown_url, timeout=60)
        md_content = md_resp.text

        # 构建输出
        output_parts = [
            f"# OCR 解析结果\n",
            f"**文件**: {filename}",
            f"**字符数**: {len(md_content)}\n",
            f"---\n",
            md_content,
        ]
        full_output = "\n".join(output_parts)

        # 保存文件
        stem = os.path.splitext(filename)[0]
        output_path = os.path.join(output_dir, f"{stem}.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_output)

        summary = (
            f"OCR 解析完成\n"
            f"**文件**: {filename}\n"
            f"**字符数**: {len(md_content)}\n"
            f"**输出路径**: {output_path}"
        )
        return [TextContent(type="text", text=summary)]

    except requests.exceptions.Timeout:
        return [TextContent(type="text", text=f"MinerU API 超时: {file_path}")]
    except Exception as e:
        return [TextContent(type="text", text=f"OCR 解析失败: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                sampling=None,
                experimental=None,
                roots=None,
            ),
            NotificationOptions(
                tools_changed=True,
                resources_changed=None,
                prompts_changed=None,
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
