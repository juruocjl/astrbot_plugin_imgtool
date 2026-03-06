# astrbot_plugin_imgtool

基于 SiliconFlow 图像生成接口的 AstrBot 插件。安装后会注册一个可被 LLM 调用的工具：

- `siliconflow_generate_image`

该工具会调用 `POST https://api.siliconflow.cn/v1/images/generations` 生成图片，并直接发送到当前会话。

## 功能

- 支持在 AstrBot 中通过函数调用（Tools / Function Calling）让 LLM 自动生图。
- API Key 在插件配置中填写，不写死到代码。
- 支持配置默认模型、默认分辨率、默认推理步数、默认 guidance scale。

## 安装

1. 将本插件放到 AstrBot 的插件目录，例如 `data/plugins/astrbot_plugin_imgtool`。
2. 安装依赖（AstrBot 会读取 `requirements.txt` 自动安装，或手动 `pip install -r requirements.txt`）。
3. 在 AstrBot WebUI 打开本插件配置，填写 `api_key`。
4. 启用插件并重载。

## 配置项

- `api_key`: SiliconFlow API Key（必填）。
- `api_base`: API 基础地址，默认 `https://api.siliconflow.cn/v1`。
- `model`: 默认模型，默认 `Kwai-Kolors/Kolors`。
- `default_image_size`: 默认分辨率，默认 `1024x1024`。
- `default_num_inference_steps`: 默认推理步数，默认 `20`。
- `default_guidance_scale`: 默认 `guidance scale`，默认 `7.5`。
- `request_timeout`: 请求超时时间（秒），默认 `90`。

## LLM 工具说明

工具名：`siliconflow_generate_image`

参数：

- `prompt` (string): 生图提示词。

说明：

- 工具对 LLM 暴露最简接口，仅保留 `prompt`。
- 模型、分辨率、推理步数等统一使用插件配置默认值。

返回：

- 文本结果。正常情况下会提示“图片已生成并直接发送到当前会话”。
- 若自动发图失败，会返回可手动打开的图片 URL 作为兜底。

## 参考文档

- AstrBot 插件开发: https://docs.astrbot.app/dev/star/plugin-new.html
- AstrBot 插件配置: https://docs.astrbot.app/dev/star/guides/plugin-config.html
- SiliconFlow 图像生成接口: https://docs.siliconflow.cn/cn/api-reference/images/images-generations
