# MinerU MCP Server

MinerU文档解析的MCP（Model Context Protocol）服务器，用于将PDF、Word、PPT、图片等文档解析为Markdown格式。

## 功能特性

- 支持PDF、DOCX、PPTX、PNG、JPG等格式
- 自动识别表格、公式、OCR
- 输出结构化Markdown格式
- 支持多语言（中文、英文、日文等）
- **智能API切换**：≤20页使用Agent轻量API（无需Token），>20页自动切换精准解析API（需Token）

## 安装依赖

```bash
pip install mcp requests PyMuPDF
```

> PyMuPDF 用于检测PDF页数，可选安装。如不安装，将默认使用Agent轻量API。

## 文件结构

```
minerU-agent-mcp/
├── mcp/
│   └── mineru_mcp_server.py  # MCP服务器主文件
└── README.md                 # 本说明文件
```

## API说明

| API类型 | 页数限制 | 文件大小 | 是否需要Token |
|---------|---------|---------|--------------|
| Agent轻量API | ≤20页 | ≤10MB | ❌ 无需 |
| 精准解析API | ≤200页 | ≤200MB | ✅ 需要 |

**获取Token：** 访问 https://mineru.net/apiManage 创建API Token

## Claude Code 初始化

### 方法1：使用 `claude mcp add` 命令

```bash
claude mcp add mineru-ocr python E:\Code\git_code\minerU-agent-mcp\mcp\mineru_mcp_server.py
```

### 方法2：手动配置

在 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "mineru-ocr": {
      "command": "python",
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"],
      "env": {
        "MINERU_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

## OpenCode 初始化

在 `~/.opencode/config.json` 中添加MCP服务器配置：

```json
{
  "mcpServers": {
    "mineru-ocr": {
      "command": "python",
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"],
      "env": {
        "MINERU_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

## Codex 初始化

在 `~/.codex/config.json` 中添加：

```json
{
  "mcpServers": {
    "mineru-ocr": {
      "command": "python",
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"],
      "env": {
        "MINERU_API_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

## 使用方法

初始化完成后，在AI编码工具中可以使用以下工具：

### parse_document

将文档解析为Markdown格式。

**参数：**
- `file_path` (必填): 待解析文件的绝对路径
- `output_dir` (可选): 输出文件夹路径，默认为源文件所在目录
- `language` (可选): 文档语言，默认为"ch"（中文）
- `page_range` (可选): 页码范围，如"1-10"或"5"
- `enable_table` (可选): 是否开启表格识别，默认为true
- `is_ocr` (可选): 是否开启OCR，默认为false
- `enable_formula` (可选): 是否开启公式识别，默认为true
- `api_token` (可选): MinerU API Token，也可通过环境变量 MINERU_API_TOKEN 设置
- `model_version` (可选): 模型版本，可选 pipeline/vlm/MinerU-HTML，默认vlm（仅精准解析API有效）

**使用示例：**

```
请帮我解析这个PDF文件：E:/documents/paper.pdf
```

AI工具会自动调用parse_document工具进行解析，并将结果保存为Markdown文件。

**解析超过20页的文档：**

```
请帮我解析这个长文档：E:/documents/long_paper.pdf（超过50页）
```

系统会自动检测页数并使用精准解析API（需要Token）。

## 智能API切换逻辑

1. 检测PDF文件页数（需要安装PyMuPDF）
2. ≤20页 → 使用Agent轻量API（无需Token，快速）
3. >20页 → 使用精准解析API（需要Token，支持大文件）
4. 非PDF文件 → 默认使用Agent轻量API

## 注意事项

1. 解析超过20页的PDF需要提供API Token
2. 获取Token：访问 https://mineru.net/apiManage
3. Token可通过环境变量 `MINERU_API_TOKEN` 设置，或在调用时传入
4. 精准解析API解析时间较长，请耐心等待
5. 支持中文、英文等多种语言的OCR识别

## 故障排除

### 问题1：导入错误
确保已安装依赖：
```bash
pip install mcp requests PyMuPDF
```

### 问题2：文件不存在
检查文件路径是否正确，使用绝对路径。

### 问题3：超过20页需要Token
提供API Token，可通过环境变量或参数传入。

### 问题4：解析失败
检查网络连接，确认文件大小和格式符合要求。

## 许可证

本项目基于MinerU开源许可证。