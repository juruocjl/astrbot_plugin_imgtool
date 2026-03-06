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

    @staticmethod
    def _is_http_url(value: str) -> bool:
        return value.startswith("http://") or value.startswith("https://")

    @staticmethod
    def _is_data_image(value: str) -> bool:
        return value.startswith("data:image/")

    def _normalize_image_ref(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if self._is_http_url(text) or self._is_data_image(text):
            return text
        return None

    def _extract_image_refs_from_obj(self, obj: Any) -> list[str]:
        refs: list[str] = []

        def add_if_valid(candidate: Any) -> None:
            ref = self._normalize_image_ref(candidate)
            if ref and ref not in refs:
                refs.append(ref)

        if obj is None:
            return refs

        # 递归处理 dict/list/tuple，兼容不同平台适配器的 raw_message 结构。
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_l = str(key).lower()
                if key_l in {
                    "url",
                    "image",
                    "img",
                    "image_url",
                    "img_url",
                    "file",
                    "src",
                    "content",
                }:
                    add_if_valid(value)
                refs.extend(self._extract_image_refs_from_obj(value))
            return list(dict.fromkeys(refs))

        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                refs.extend(self._extract_image_refs_from_obj(item))
            return list(dict.fromkeys(refs))

        # 尝试从消息组件对象常见属性里提取图片链接。
        for attr in ("url", "image", "img", "image_url", "img_url", "file", "src"):
            if hasattr(obj, attr):
                add_if_valid(getattr(obj, attr, None))

        # 某些组件对象有 to_dict / __dict__。
        if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
            try:
                refs.extend(self._extract_image_refs_from_obj(obj.to_dict()))
            except Exception:
                pass
        elif hasattr(obj, "__dict__"):
            refs.extend(self._extract_image_refs_from_obj(vars(obj)))

        return list(dict.fromkeys(refs))

    @staticmethod
    def _normalize_message_id(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _extract_first_image_by_message_id(self, obj: Any, target_message_id: str) -> str | None:
        target = self._normalize_message_id(target_message_id)
        if not target:
            return None

        def walk(node: Any) -> str | None:
            if node is None:
                return None

            if isinstance(node, dict):
                # 常见消息 ID 字段
                for id_key in ("message_id", "msg_id", "id"):
                    if self._normalize_message_id(node.get(id_key)) == target:
                        refs = self._extract_image_refs_from_obj(node)
                        if refs:
                            return refs[0]
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
                return None

            if isinstance(node, (list, tuple, set)):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
                return None

            # 处理对象形式消息
            for id_attr in ("message_id", "msg_id", "id"):
                if hasattr(node, id_attr) and self._normalize_message_id(getattr(node, id_attr, None)) == target:
                    refs = self._extract_image_refs_from_obj(node)
                    if refs:
                        return refs[0]

            if hasattr(node, "to_dict") and callable(getattr(node, "to_dict")):
                try:
                    return walk(node.to_dict())
                except Exception:
                    return None

            if hasattr(node, "__dict__"):
                return walk(vars(node))

            return None

        return walk(obj)

    def _get_first_reference_image(
        self,
        event: AstrMessageEvent,
        reference_message_id: str = "",
    ) -> str | None:
        ref_mid = self._normalize_message_id(reference_message_id)

        # 当指定了 reference_message_id 时，优先在当前事件可见数据中按 ID 匹配。
        if ref_mid:
            current_mid = self._normalize_message_id(getattr(event.message_obj, "message_id", None))
            if current_mid == ref_mid:
                refs = self._extract_image_refs_from_obj(getattr(event.message_obj, "message", None))
                if refs:
                    return refs[0]

            # 在 raw_message（含回复/引用上下文）中递归按消息 ID 查找
            raw_message = getattr(event.message_obj, "raw_message", None)
            matched = self._extract_first_image_by_message_id(raw_message, ref_mid)
            if matched:
                return matched

            # 在 message_obj 里继续尝试
            matched = self._extract_first_image_by_message_id(event.message_obj, ref_mid)
            if matched:
                return matched

        # 未指定或未找到时，回退到当前消息第一张图。
        current_message = getattr(event.message_obj, "message", None)
        refs = self._extract_image_refs_from_obj(current_message)
        if refs:
            return refs[0]

        # 2) 兼容 get_messages
        if hasattr(event, "get_messages") and callable(getattr(event, "get_messages")):
            try:
                refs = self._extract_image_refs_from_obj(event.get_messages())
                if refs:
                    return refs[0]
            except Exception:
                pass

        # 3) 兜底：引用/回复消息通常在 raw_message 里
        raw_message = getattr(event.message_obj, "raw_message", None)
        refs = self._extract_image_refs_from_obj(raw_message)
        if refs:
            return refs[0]

        return None

    async def _generate_image(
        self,
        *,
        prompt: str,
        reference_image: str | None = None,
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
        if reference_image:
            payload["image"] = reference_image
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
        reference_message_id: str = "",
    ) -> str:
        """使用 SiliconFlow 生成图片并直接发送到当前会话。

        Args:
            prompt(string): 生图提示词。
            reference_message_id(string): 可选，参考图所在的消息 ID。若不存在则回退使用当前消息中的第一张图片。

        说明:
            对 LLM 暴露简化接口，仅需 prompt，可选指定 reference_message_id。
            模型、分辨率、步数等参数统一使用插件配置中的默认值。
        """
        try:
            reference_image = self._get_first_reference_image(event, reference_message_id)
            image_url = await self._generate_image(
                prompt=prompt,
                reference_image=reference_image,
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
