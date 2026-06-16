# Vision MCP Server

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

A configurable Model Context Protocol (MCP) server that enables AI assistants to understand and analyze **images, audio, and video** using multimodal vision models. Supports multiple providers with easy switching.

### Features

- **Multi-Provider Support**: Configure multiple vision model providers, switch via parameter
- **Image Recognition**: Describe, analyze, and extract information from images
- **Audio Recognition**: Speech-to-text, music genre detection, audio content analysis
- **Video Recognition**: Video content description, scene analysis, action recognition
- **Batch Processing**: Support for multiple files in a single request
- **Flexible Auth**: Supports both `Bearer` and `api-key` authentication styles
- **Robust Error Handling**: Comprehensive input validation and retry mechanisms

### Installation

```bash
git clone <repo-url>
cd mode-media-recognition-mcp
python -m venv .venv
# Windows
.venv\Scripts\pip install -e .
# Linux/Mac
source .venv/bin/activate && pip install -e .
```

### Configuration

#### Option 1: Environment Variables (Single Provider)

```bash
claude mcp add vision-mcp --scope user \
  --env VISION_API_KEY="your-api-key" \
  --env VISION_API_BASE="https://api.xiaomimimo.com/v1" \
  --env VISION_MODEL="mimo-v2-omni" \
  --env VISION_AUTH_TYPE="api-key" \
  -- "/path/to/.venv/bin/python" -m mimo_media_recognition_mcp.server
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VISION_API_KEY` | Yes | - | API key |
| `VISION_API_BASE` | Yes | - | API endpoint URL |
| `VISION_MODEL` | Yes | - | Model name |
| `VISION_AUTH_TYPE` | No | `bearer` | Auth type: `bearer` or `api-key` |
| `VISION_PROVIDER_NAME` | No | `default` | Provider display name |
| `VISION_TIMEOUT` | No | `180` | HTTP timeout in seconds |

#### Option 2: Config File (Multiple Providers)

1. Copy the example config:

```bash
cp providers.example.json providers.json
```

2. Edit `providers.json`:

```json
{
  "providers": {
    "mimo": {
      "api_base": "https://api.xiaomimimo.com/v1",
      "api_key_env": "MIMO_API_KEY",
      "model": "mimo-v2-omni",
      "auth_type": "api-key"
    },
    "qwen": {
      "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key_env": "QWEN_API_KEY",
      "model": "qwen-vl-max",
      "auth_type": "bearer"
    }
  },
  "default_provider": "mimo"
}
```

3. Register with Claude Code:

```bash
claude mcp add vision-mcp --scope user \
  --env MIMO_API_KEY="your-mimo-key" \
  --env QWEN_API_KEY="your-qwen-key" \
  --env VISION_PROVIDERS_FILE="/path/to/providers.json" \
  -- "/path/to/.venv/bin/python" -m mimo_media_recognition_mcp.server
```

### Usage

```
Analyze this image: /path/to/photo.jpg
Transcribe this audio: /path/to/recording.mp3
Describe this video: /path/to/video.mp4
```

To use a specific provider:

```
Use qwen to analyze this image: /path/to/photo.jpg
```

### Available Tools

| Tool | Description |
|------|-------------|
| `understand_image` | Analyze images (JPEG, PNG, WebP, GIF, BMP) |
| `understand_audio` | Analyze audio (MP3, WAV, M4A, OGG, FLAC, AAC) |
| `understand_video` | Analyze video (MP4, MOV, AVI, MKV, WebM, FLV) |
| `list_providers` | List all configured vision providers |

All tools accept an optional `provider` parameter to select which vision provider to use.

### Acknowledgments

This project was inspired by [congxxx/mimo-media-recognition-mcp](https://github.com/congxxx/mimo-media-recognition-mcp).

### License

MIT License - see [LICENSE](LICENSE) for details.

---

<a name="中文"></a>
## 中文

可配置的 MCP 服务器，让 AI 助手使用多模态视觉模型理解和分析**图片、音频和视频**。支持多 provider 切换。

### 功能特性

- **多 Provider 支持**：配置多个视觉模型，通过参数切换
- **图片识别**：描述、分析图片，提取信息
- **音频识别**：语音转文字、音乐风格检测、音频内容分析
- **视频识别**：视频内容描述、场景分析、动作识别
- **批量处理**：单次请求支持多个文件
- **灵活鉴权**：支持 `Bearer` 和 `api-key` 两种认证方式
- **健壮的错误处理**：完善的输入验证和重试机制

### 安装

```bash
git clone <repo-url>
cd mode-media-recognition-mcp
python -m venv .venv
# Windows
.venv\Scripts\pip install -e .
# Linux/Mac
source .venv/bin/activate && pip install -e .
```

### 配置

#### 方式一：环境变量（单 Provider）

```bash
claude mcp add vision-mcp --scope user \
  --env VISION_API_KEY="你的 API Key" \
  --env VISION_API_BASE="https://api.xiaomimimo.com/v1" \
  --env VISION_MODEL="mimo-v2-omni" \
  --env VISION_AUTH_TYPE="api-key" \
  -- "/path/to/.venv/bin/python" -m mimo_media_recognition_mcp.server
```

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `VISION_API_KEY` | 是 | - | API 密钥 |
| `VISION_API_BASE` | 是 | - | API 请求地址 |
| `VISION_MODEL` | 是 | - | 模型名称 |
| `VISION_AUTH_TYPE` | 否 | `bearer` | 鉴权方式：`bearer` 或 `api-key` |
| `VISION_PROVIDER_NAME` | 否 | `default` | Provider 显示名称 |
| `VISION_TIMEOUT` | 否 | `180` | HTTP 超时秒数 |

#### 方式二：配置文件（多 Provider）

1. 复制示例配置：

```bash
cp providers.example.json providers.json
```

2. 编辑 `providers.json`：

```json
{
  "providers": {
    "mimo": {
      "api_base": "https://api.xiaomimimo.com/v1",
      "api_key_env": "MIMO_API_KEY",
      "model": "mimo-v2-omni",
      "auth_type": "api-key"
    },
    "qwen": {
      "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "api_key_env": "QWEN_API_KEY",
      "model": "qwen-vl-max",
      "auth_type": "bearer"
    }
  },
  "default_provider": "mimo"
}
```

3. 注册到 Claude Code：

```bash
claude mcp add vision-mcp --scope user \
  --env MIMO_API_KEY="你的 MIMO Key" \
  --env QWEN_API_KEY="你的 Qwen Key" \
  --env VISION_PROVIDERS_FILE="/path/to/providers.json" \
  -- "/path/to/.venv/bin/python" -m mimo_media_recognition_mcp.server
```

### 使用

```
分析这张图片：/path/to/photo.jpg
转录这段音频：/path/to/recording.mp3
描述这个视频：/path/to/video.mp4
```

指定 provider：

```
用 qwen 分析这张图片：/path/to/photo.jpg
```

### 可用工具

| 工具 | 说明 |
|------|------|
| `understand_image` | 分析图片（JPEG、PNG、WebP、GIF、BMP） |
| `understand_audio` | 分析音频（MP3、WAV、M4A、OGG、FLAC、AAC） |
| `understand_video` | 分析视频（MP4、MOV、AVI、MKV、WebM、FLV） |
| `list_providers` | 列出所有已配置的 provider |

所有工具都支持可选的 `provider` 参数来选择使用哪个视觉 provider。

### 致谢

本项目灵感来源于 [congxxx/mimo-media-recognition-mcp](https://github.com/congxxx/mimo-media-recognition-mcp)。

### 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)。
