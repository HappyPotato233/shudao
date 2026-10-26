"""隐患视觉识别：OpenAI 兼容多模态调用。"""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

import cv2
from fastapi import UploadFile
from openai import OpenAI

from app.core.config import settings
from app.core.response import BizError, ErrorCode
from app.services.annotator import annotate, extract_json_array, imread_unicode
from app.services.storage import public_url, save_upload

# 模型调用超时上界（秒）与重试次数：防止挂起拖死前端 loading
API_TIMEOUT_S = 120
API_MAX_RETRIES = 1
# 送入模型前图片长边压缩上限（像素）：减小 base64 体积，加快识别
MAX_SIDE = 1280


SYSTEM_PROMPT = (
    "你是施工场景安全隐患识别专家。\n"
    "任务规则：\n"
    "1. 图中检测到的物体本身大部分属于正常设施，物体存在不等于隐患。只有物体发生破损、缺失、违规摆放、不符合安全规范，才判定为隐患；全部物体状态正常则直接输出空数组[]。\n"
    "2. 参考物体类别列表：\n"
    "【加油站场景】\n"
    "0: fangzhuanglan #防撞栏\n"
    "1: jiayouqiang #加油枪\n"
    "2: jiayouji #加油机\n"
    "3: miehuoqi #灭火器\n"
    "4: zhuixingtong #锥形桶\n"
    "5: push_extinguisher #手推灭火器\n"
    "6: support_pillar #支撑柱/立柱\n"
    "7: fuel_hose #加油机输油软管\n"
    "8: vent_pipe #通气管\n"
    "9: oil_discharge_port #卸油口\n"
    "10: static_release_post #静电释放桩\n"
    "11: static_wire #静电线\n"
    "12: static_clip #静电夹\n"
    "13: power_distribution_box #配电箱\n"
    "【桥梁工地】\n"
    "0: rebar_cage #钢筋笼\n"
    "1: hopper #料斗\n"
    "2: broken_pile #破碎桩头\n"
    "3: rebar_cap #钢筋承台\n"
    "4: cylindrical_pier_formwork #圆柱墩模板\n"
    "5: cylindrical_pier #圆柱墩\n"
    "6: tie_beam_formwork #盖系梁\n"
    "7: precast_beam_slab #预制梁板\n"
    "8: beam_transport_vehicle #运梁车\n"
    "9: concrete_paver #混凝土摊铺机\n"
    "10: wet_joint #湿接缝\n"
    "【隧道施工】\n"
    "0: tunnel_portal_guide_wall #洞口导向墙\n"
    "1: drainage_ditch #排水沟\n"
    "2: excavator #挖掘机\n"
    "3: muck_truck #运渣车\n"
    "4: bulldozer #推土机\n"
    "5: concrete_pump #混凝土输送泵\n"
    "6: rock_drill_jumbo #凿岩钻臂\n"
    "7: ventilation_duct #通风风带\n"
    "8: ventilation_fan #通风机\n"
    "9: invert_platform #仰拱栈桥\n"
    "【收费站隧道公路】\n"
    "0: toll_booth #收费亭\n"
    "1: lane_indicator #车道指示器\n"
    "2: toll_display #费额显示屏\n"
    "3: toll_bar #收费杆\n"
    "4: anti_collision_pier #防撞墩\n"
    "5: lane_sign #车道标识牌\n"
    "6: anti_collision_bucket #防撞桶\n"
    "7: monitoring_equipment #监控设备\n"
    "8: etc_antenna #ETC天线\n"
    "9: truck_scale #货车称台\n"
    "10: fire_box #消防箱\n"
    "11: fire_pool #消防水池\n"
    "12: drainage_ditch #排水沟\n"
    "13: led_screen #电子显示屏\n"
    "14: zhuixingtong #锥形桶\n"
    "15: slope #边坡\n"
    "16: tunnel_entrance #隧道洞口\n"
    "17: tunnel_body #隧道洞身\n"
    "18: tunnel_fan #隧道风机\n"
    "19: emergency_phone #紧急电话\n"
    "20: tunnel_lighting #隧道照明\n"
    "21: culvert #涵洞\n"
    "22: wave_guardrail #波形护栏\n"
    "23: roadside_plant #路侧植株\n"
    "24: central_plant #中央植株\n"
    "25: gore_area_plant #三角区植株\n"
    "26: warning_sign #预警标识\n"
    "27: road_marking #标线\n"
    "28: anti_glare_board #防眩板\n"
    "29: sound_barrier #声屏障\n"
    "30: parking #停车位\n"
    "31: bridge_bearing #桥梁支座\n"
    "32: pipeline #管道\n"
    "3. risk风险等级判定规则：\n"
    "high(高风险): 会直接引发爆炸、坍塌、触电、重大伤亡；color_bgr=[0,0,255]\n"
    "medium(中风险): 存在明显违规，长期会引发事故；color_bgr=[0,165,255]\n"
    "low(低风险): 轻微不规范，无即刻重大危险；color_bgr=[0,255,0]\n"
    "4. 输出严格JSON数组，禁止任何解释、说明、markdown。无隐患输出[]。\n"
    "数组每一个对象字段：\n"
    "id：整数，隐患对应物体的类别ID；\n"
    "label：字符串，隐患具体名称，不能直接写原始物体名，要描述异常状态，例\"灭火器缺失\"，而不是\"灭火器\"；\n"
    "risk：只能是 high / medium / low；\n"
    "bbox_norm：[x1,y1,x2,y2]，归一化坐标0‑1，x1<x2,y1<y2；\n"
    "bbox_px：[x1,y1,x2,y2]像素坐标，可省略；\n"
    "color_bgr：[B,G,R]数组，严格匹配risk对应的BGR数值；\n"
    "conf：0‑1浮点数，识别置信度；\n"
    "fix：字符串，针对性整改建议；\n"
    "note：字符串，描述物体在图片的位置。"
)



def is_configured() -> bool:
    return bool(
        settings.VISULIZATION_API_KEY
        and settings.VISULIZATION_BASE_URL
        and settings.VISULIZATION_MODEL_NAME
    )


def _encode_image_small(image_path: Path) -> str:
    """图片长边压到 MAX_SIDE 后编码为 data URL，减小请求体积加快识别。"""
    img = imread_unicode(image_path)
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("图片编码失败")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _call_vision_api(client: OpenAI, model: str, image_path: Path, title: str | None, description: str | None) -> str:
    h, w = imread_unicode(image_path).shape[:2]
    size_hint = f"原图像素尺寸: width={w}, height={h}。请据此填写 bbox_px 与 bbox_norm。"
    parts = [p for p in (title, description) if p]
    content_text = ("\n".join(parts) + "\n\n" + size_hint) if parts else size_hint
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": content_text},
                {"type": "image_url", "image_url": {"url": _encode_image_small(image_path)}},
            ],
        },
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        # qwen3.x 为思考模型：默认思考链使识别耗时 90s+ 直至超时，关闭后秒级返回
        extra_body={"enable_thinking": False},
    )
    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("模型返回空内容")
    return content


def detect(image_path: Path, title: str | None = None, description: str | None = None) -> list[dict]:
    if not is_configured():
        raise BizError(*ErrorCode.AI_UNAVAILABLE)
    client = OpenAI(
        api_key=settings.VISULIZATION_API_KEY,
        base_url=settings.VISULIZATION_BASE_URL,
        timeout=API_TIMEOUT_S,
        max_retries=API_MAX_RETRIES,
    )
    try:
        raw = _call_vision_api(client, settings.VISULIZATION_MODEL_NAME, image_path, title, description)
        return extract_json_array(raw)
    except BizError:
        raise
    except Exception:
        raise BizError(*ErrorCode.AI_UNAVAILABLE)


def detect_and_annotate(files: list[UploadFile], title: str | None = None, description: str | None = None) -> list[dict]:
    if not is_configured():
        raise BizError(*ErrorCode.AI_UNAVAILABLE)
    if len(files) > settings.MAX_HAZARD_IMAGES:
        raise BizError(*ErrorCode.IMAGE_COUNT_EXCEEDED)
    items = []
    for index, file in enumerate(files):
        rel, _size = save_upload(file, "hazards/ai_tmp")
        image_path = Path(settings.UPLOAD_DIR) / rel
        detections = detect(image_path, title, description)
        annotated_rel = rel.replace(".", f"_annotated_{index}.")
        annotated_path = Path(settings.UPLOAD_DIR) / annotated_rel
        drawn = annotate(image_path, detections, annotated_path)
        items.append(
            {
                "image_index": index,
                "original_url": public_url(rel),
                "annotated_url": public_url(annotated_rel),
                "detections": drawn,
            }
        )
    return items
