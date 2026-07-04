"""
MCP Server for MinerU Document OCR API.
Supports both Agent lightweight API (≤20 pages) and Precise API (>20 pages).
"""
import asyncio
import json
import sys
import os
import time
import zipfile
import tempfile
import requests
from io import BytesIO
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

AGENT_BASE_URL = "https://mineru.net/api/v1/agent"
PRECISE_BASE_URL = "https://mineru.net/api/v4"
AGENT_PAGE_LIMIT = 20
REQUEST_TIMEOUT = 300  # seconds
POLL_INTERVAL = 3  # seconds

server = Server("mineru-ocr")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="parse_document",
            description="使用 MinerU 引擎将文档（PDF/Word/PPT/图片）解析为 Markdown 格式并保存到指定文件夹。"
            "支持 PDF、DOCX、PPTX、PNG、JPG 等格式。"
            "≤20页使用Agent轻量API（无需Token），>20页自动切换精准解析API（需Token）。"
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
                    "api_token": {
                        "type": "string",
                        "description": "MinerU API Token（精准解析API需要）。可从 https://mineru.net/apiManage 获取。也可通过环境变量 MINERU_API_TOKEN 设置。",
                        "default": None,
                    },
                    "model_version": {
                        "type": "string",
                        "description": "模型版本：pipeline（默认）、vlm、MinerU-HTML。仅精准解析API有效。",
                        "default": "vlm",
                    },
                },
                "required": ["file_path"],
            },
        )
    ]


def _get_pdf_page_count(file_path):
    """获取PDF文件页数"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        page_count = doc.page_count
        doc.close()
        return page_count
    except ImportError:
        return None
    except Exception:
        return None


def _get_upload_url(file_name, language, page_range, enable_table, is_ocr, enable_formula):
    """获取 MinerU Agent 轻量API签名上传 URL"""
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
        f"{AGENT_BASE_URL}/parse/file",
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


def _poll_agent_result(task_id, timeout=300):
    """轮询查询 Agent API 解析结果"""
    state_labels = {
        "uploading": "文件下载中",
        "pending": "排队中",
        "running": "解析中",
        "waiting-file": "等待文件上传",
    }
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{AGENT_BASE_URL}/parse/{task_id}",
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


def _create_precise_task(file_path, token, language, page_range, enable_table, is_ocr, enable_formula, model_version):
    """创建精准解析API任务"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # 获取文件URL（需要先上传到可访问的URL）
    # 这里我们使用文件上传模式
    file_name = os.path.basename(file_path)
    
    # 先获取批量上传链接
    data = {
        "files": [{"name": file_name}],
        "model_version": model_version,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
    }
    
    resp = requests.post(
        f"{PRECISE_BASE_URL}/file-urls/batch",
        headers=headers,
        json=data,
        timeout=30,
    )
    result = resp.json()
    if result["code"] != 0:
        raise Exception(f"获取上传链接失败: {result['msg']}")
    
    batch_id = result["data"]["batch_id"]
    file_url = result["data"]["file_urls"][0]
    
    # 上传文件
    with open(file_path, "rb") as f:
        resp = requests.put(file_url, data=f, timeout=REQUEST_TIMEOUT)
    if resp.status_code not in (200, 201):
        raise Exception(f"文件上传失败, HTTP {resp.status_code}")
    
    return batch_id


def _poll_precise_result(batch_id, token, timeout=600):
    """轮询查询精准解析API结果"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    state_labels = {
        "pending": "排队中",
        "running": "解析中",
        "converting": "格式转换中",
    }
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(
            f"{PRECISE_BASE_URL}/extract-results/batch/{batch_id}",
            headers=headers,
            timeout=30,
        )
        result = resp.json()
        extract_result = result["data"]["extract_result"][0]
        state = extract_result["state"]
        elapsed = int(time.time() - start)

        if state == "done":
            return extract_result["full_zip_url"]
        if state == "failed":
            err_msg = extract_result.get("err_msg", "未知错误")
            raise Exception(f"解析失败: {err_msg}")

        time.sleep(POLL_INTERVAL)

    raise Exception(f"轮询超时 ({timeout}s)")


def _download_and_extract_zip(zip_url, output_dir, filename):
    """下载ZIP包并解压获取Markdown"""
    resp = requests.get(zip_url, timeout=120)
    if resp.status_code != 200:
        raise Exception(f"下载ZIP包失败: HTTP {resp.status_code}")
    
    stem = os.path.splitext(filename)[0]
    md_output_path = os.path.join(output_dir, f"{stem}.md")
    
    with tempfile.ZipFile(BytesIO(resp.content)) as zf:
        # 查找full.md文件
        md_files = [f for f in zf.namelist() if f.endswith('full.md')]
        if not md_files:
            # 尝试查找任何.md文件
            md_files = [f for f in zf.namelist() if f.endswith('.md')]
        
        if md_files:
            with zf.open(md_files[0]) as md_file:
                md_content = md_file.read().decode('utf-8')
        else:
            raise Exception("ZIP包中未找到Markdown文件")
    
    return md_content, md_output_path


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
    api_token = arguments.get("api_token", None) or os.environ.get("MINERU_API_TOKEN")
    model_version = arguments.get("model_version", "vlm")

    if not os.path.isfile(file_path):
        return [TextContent(type="text", text=f"错误：文件不存在 — {file_path}")]

    if not output_dir:
        output_dir = os.path.dirname(os.path.abspath(file_path))

    filename = os.path.basename(file_path)
    
    # 检测文件页数
    page_count = None
    if filename.lower().endswith('.pdf'):
        page_count = _get_pdf_page_count(file_path)
    
    # 判断使用哪个API
    use_precise_api = False
    if page_count is not None and page_count > AGENT_PAGE_LIMIT:
        if not api_token:
            return [TextContent(type="text", text=f"错误：文件有 {page_count} 页，超过Agent API限制（{AGENT_PAGE_LIMIT}页）。请提供API Token以使用精准解析API。可从 https://mineru.net/apiManage 获取Token。")]
        use_precise_api = True

    try:
        if use_precise_api:
            # 使用精准解析API
            batch_id = _create_precise_task(
                file_path, api_token, language, page_range, 
                enable_table, is_ocr, enable_formula, model_version
            )
            zip_url = _poll_precise_result(batch_id, api_token, timeout=REQUEST_TIMEOUT * 2)
            md_content, output_path = _download_and_extract_zip(zip_url, output_dir, filename)
        else:
            # 使用Agent轻量API
            task_id, file_url = _get_upload_url(
                filename, language, page_range, enable_table, is_ocr, enable_formula
            )
            _upload_file(file_path, file_url)
            markdown_url = _poll_agent_result(task_id, timeout=REQUEST_TIMEOUT)
            md_resp = requests.get(markdown_url, timeout=60)
            md_content = md_resp.text
            
            stem = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{stem}.md")

        # 构建输出
        output_parts = [
            f"# OCR 解析结果\n",
            f"**文件**: {filename}",
            f"**字符数**: {len(md_content)}\n",
            f"**解析方式**: {'精准解析API' if use_precise_api else 'Agent轻量API'}\n",
            f"---\n",
            md_content,
        ]
        full_output = "\n".join(output_parts)

        # 保存文件
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_output)

        summary = (
            f"OCR 解析完成\n"
            f"**文件**: {filename}\n"
            f"**字符数**: {len(md_content)}\n"
            f"**解析方式**: {'精准解析API' if use_precise_api else 'Agent轻量API'}\n"
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