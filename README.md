# MinerU MCP Server

MinerU文档解析的MCP（Model Context Protocol）服务器，用于将PDF、Word、PPT、图片等文档解析为Markdown格式。

## 功能特性

- 支持PDF、DOCX、PPTX、PNG、JPG等格式
- 自动识别表格、公式、OCR
- 输出结构化Markdown格式
- 支持多语言（中文、英文、日文等）

## 安装依赖

```bash
pip install mcp requests
```

## 文件结构

```
minerU-agent-mcp/
├── mcp/
│   └── mineru_mcp_server.py  # MCP服务器主文件
└── README.md                 # 本说明文件
```

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
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"]
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
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"]
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
      "args": ["E:\\Code\\git_code\\minerU-agent-mcp\\mcp\\mineru_mcp_server.py"]
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

**使用示例：**

```
请帮我解析这个PDF文件：E:/documents/paper.pdf
```

AI工具会自动调用parse_document工具进行解析，并将结果保存为Markdown文件。

## API限制

- 文件大小限制：10MB
- 页数限制：20页
- 支持格式：PDF、DOCX、PPTX、PNG、JPG

## 注意事项

1. 需要网络连接访问MinerU API
2. 大文件解析可能需要较长时间
3. 解析结果会自动保存到源文件所在目录或指定目录
4. 支持中文、英文等多种语言的OCR识别

## 故障排除

### 问题1：导入错误
确保已安装依赖：
```bash
pip install mcp requests
```

### 问题2：文件不存在
检查文件路径是否正确，使用绝对路径。

### 问题3：解析失败
检查网络连接，确认文件大小和格式符合要求。

## 许可证

本项目基于MinerU开源许可证。