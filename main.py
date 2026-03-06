import re
from typing import Any

import httpx
import astrbot.api.message_components as Comp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star, register


@register("astrbot_plugin_imgtool", "cjlqwq", "硅基流动生图工具插件", "1.0.0")
class SiliconFlowImageToolPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    async def initialize(self):
        """插件初始化。"""
        logger.info("[astrbot_plugin_imgtool] plugin initialized")

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        value = self.config.get(key, default)
        if isinstance(value, str):
            return value.strip()
        return value

    def _get_api_key(self) -> str:
        api_key = self._get_config_value("api_key", "")
        if not api_key:
            raise ValueError("未配置 SiliconFlow API Key，请在插件配置中填写 api_key。")
        return api_key

    async def _generate_image(
        self,
        *,
        prompt: str,
        negative_prompt: str | None = None,
        image_size: str | None = None,
        model: str | None = None,
        num_inference_steps: int | None = None,
        guidance_scale: float | None = None,
        seed: int | None = None,
    ) -> str:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("prompt 不能为空。")

        if image_size and not re.fullmatch(r"\d+x\d+", image_size):
            raise ValueError("image_size 格式错误，应为例如 1024x1024。")

        api_base = self._get_config_value("api_base", "https://api.siliconflow.cn/v1")
        default_model = self._get_config_value("model", "Kwai-Kolors/Kolors")
        default_size = self._get_config_value("default_image_size", "1024x1024")
        default_steps = int(self._get_config_value("default_num_inference_steps", 20))
        default_guidance = float(self._get_config_value("default_guidance_scale", 7.5))

        payload: dict[str, Any] = {
            "model": (model or default_model).strip(),
            "prompt": prompt,
            "image_size": (image_size or default_size).strip(),
            "num_inference_steps": num_inference_steps if num_inference_steps is not None else default_steps,
            "guidance_scale": guidance_scale if guidance_scale is not None else default_guidance,
        }

        if negative_prompt:
            payload["negative_prompt"] = negative_prompt.strip()
        if seed is not None and seed >= 0:
            payload["seed"] = seed

        url = f"{api_base.rstrip('/')}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }

        timeout = float(self._get_config_value("request_timeout", 90))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            text = response.text.strip()
            detail = text[:300] if text else "no detail"
            raise RuntimeError(f"SiliconFlow 接口请求失败: HTTP {response.status_code}, {detail}")

        data = response.json()
        images = data.get("images") or []
        if not images or not isinstance(images, list):
            raise RuntimeError("SiliconFlow 返回异常：缺少 images 字段。")

        image_url = images[0].get("url") if isinstance(images[0], dict) else None
        if not image_url:
            raise RuntimeError("SiliconFlow 返回异常：未拿到图片 URL。")
        return image_url

    @filter.llm_tool(name="siliconflow_generate_image")
    async def siliconflow_generate_image(
        self,
        event: AstrMessageEvent,
        prompt: str,
        image_size: str = "",
        negative_prompt: str = "",
        model: str = "",
        num_inference_steps: int = 0,
        guidance_scale: float = 0.0,
        seed: int = -1,
    ) -> str:
        """使用 SiliconFlow 生成图片，返回图片 URL。

        Args:
            prompt(string): 生图提示词。
            image_size(string): 图片分辨率，格式为 widthxheight，例如 1024x1024。留空使用插件默认值。
            negative_prompt(string): 负面提示词，可选。
            model(string): 模型名，可选，留空使用配置中的默认模型。
            num_inference_steps(number): 推理步数，可选，传 0 时使用配置默认值。
            guidance_scale(number): 提示词遵循强度，可选，传 0 时使用配置默认值。
            seed(number): 随机种子，可选，传 -1 表示不指定。
        """
        _ = event
        try:
            image_url = await self._generate_image(
                prompt=prompt,
                negative_prompt=negative_prompt or None,
                image_size=image_size or None,
                model=model or None,
                num_inference_steps=num_inference_steps if num_inference_steps > 0 else None,
                guidance_scale=guidance_scale if guidance_scale > 0 else None,
                seed=seed if seed >= 0 else None,
            )

            # 直接把图片发到当前会话，用户无需再点开 URL。
            try:
                chain = MessageChain([Comp.Image.fromURL(image_url)])
                await self.context.send_message(event.unified_msg_origin, chain)
                return "图片已生成并直接发送到当前会话。"
            except Exception as send_exc:
                logger.warning(f"send generated image failed: {send_exc}")
                return (
                    "图片生成成功，但自动发送图片失败。"
                    f"你可以手动打开链接: {image_url}。"
                )
        except Exception as exc:
            logger.warning(f"siliconflow_generate_image failed: {exc}")
            return f"图片生成失败: {exc}"

    async def terminate(self):
        """插件卸载/停用时调用。"""
        logger.info("[astrbot_plugin_imgtool] plugin terminated")
