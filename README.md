# astrbot_plugin_imgtool

基于 SiliconFlow 图像生成接口的 AstrBot 插件。安装后会注册一个可被 LLM 调用的工具：

- `siliconflow_generate_image`

该工具会调用 `POST https://api.siliconflow.cn/v1/images/generations` 生成图片，并返回图片 URL。

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
- `image_size` (string): 可选，格式 `宽x高`，如 `1024x1024`。
- `negative_prompt` (string): 可选。
- `model` (string): 可选，不传则使用配置默认模型。
- `num_inference_steps` (number): 可选，传 `0` 时走默认值。
- `guidance_scale` (number): 可选，传 `0` 时走默认值。
- `seed` (number): 可选，传 `-1` 表示不指定。

返回：

- 文本结果，包含生成图片 URL（该 URL 一般约 1 小时后过期，请尽快下载保存）。

## 参考文档

- AstrBot 插件开发: https://docs.astrbot.app/dev/star/plugin-new.html
- AstrBot 插件配置: https://docs.astrbot.app/dev/star/guides/plugin-config.html
- SiliconFlow 图像生成接口: https://docs.siliconflow.cn/cn/api-reference/images/images-generations
