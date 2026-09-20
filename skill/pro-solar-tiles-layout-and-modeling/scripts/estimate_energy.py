#!/usr/bin/env python3
"""Simple, traceable energy estimates for 70 W Almaden Pro PV tiles; stdlib only."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
DOCS = "https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en"
MANUAL = "https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en"
TILE_POWER_W = 70
SYSTEM_EFFICIENCY = 0.88
LIMITATIONS = [
    "Pro 光伏平瓦按各坡真实平面倾角和朝向估算；未计算组件局部失配、旁路二极管或现场逐时近遮挡。",
    "未使用本型号 PAN 或实测发电校准；结果为简单发电量估算，不是本组件的精确性能仿真。",
    "估算结果不代表指定未来年份的实际发电；不模拟并网、储能、逆变器选型、限电或经济收益。",
]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number(value, label, low=0, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} 必须是有限数值")
    if value < low or (high is not None and value > high):
        raise ValueError(f"{label} 超出允许范围 {low} 至 {high if high is not None else '无限制'}")
    return float(value)


def _cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _monthly(values):
    return [{"month": i + 1, "energy_kwh": value / 100} for i, value in enumerate(values)]


def _allocate_months(annual_cents, weights):
    if not sum(weights):
        if annual_cents:
            raise ValueError("正年发电量缺少可用的月分布，不能虚构月度结果")
        return _monthly([0] * 12)
    exact = [annual_cents * value / sum(weights) for value in weights]
    cents = [math.floor(value) for value in exact]
    order = sorted(range(12), key=lambda i: exact[i] - cents[i], reverse=True)
    for i in order[:annual_cents - sum(cents)]:
        cents[i] += 1
    return _monthly(cents)


def _faces(layout):
    if not isinstance(layout, dict) or not isinstance(layout.get("faces"), list):
        raise ValueError("layout.faces 必须是数组")
    result, ids = [], set()
    for face in layout["faces"]:
        if not isinstance(face, dict) or not isinstance(face.get("id"), str) or not face["id"].strip():
            raise ValueError("每个屋面必须有非空字符串 id")
        if face["id"] in ids:
            raise ValueError(f"重复屋面 id: {face['id']}，已停止以免重复累计")
        ids.add(face["id"])
        if not isinstance(face.get("tiles"), list):
            raise ValueError(f"屋面 {face['id']} 缺少 tiles 数组")
        tile_ids, count = set(), 0
        for tile in face["tiles"]:
            if not isinstance(tile, dict) or tile.get("kind") not in ("pv", "companion"):
                raise ValueError(f"屋面 {face['id']} 的瓦片 kind 只能是 pv 或 companion")
            if tile["kind"] == "pv" and tile.get("stock_type", "full") != "full":
                raise ValueError("Pro 发电瓦只允许完整70 W整瓦；半瓦为非发电配瓦")
            if "id" in tile:
                key = str(tile["id"])
                if key in tile_ids:
                    raise ValueError(f"屋面 {face['id']} 内重复瓦片 id: {key}")
                tile_ids.add(key)
            count += tile["kind"] == "pv"
        result.append({"id": face["id"], "name": str(face.get("name", face["id"])),
                       "pv_tiles": count, "power_kwp": count * TILE_POWER_W / 1000,
                       "annual_kwh": None, "monthly_kwh": None, "warnings": []})
    return result


def _fetch(params, output_dir, index, face):
    """Keep the actual request and unmodified response, including HTTP errors."""
    raw_dir = output_dir / "energy_raw"
    raw_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"pvgis-{index + 1:03d}-{stamp}"
    url = API + "?" + urlencode(params)
    record = {"face_id": face["id"], "requested_at_utc": _now(), "url": url,
              "parameters": params, "documentation_url": DOCS}
    raw_path = raw_dir / (prefix + ".response.json")
    request_path = raw_dir / (prefix + ".request.json")
    face["provenance"] = {"request_file": str(request_path.relative_to(output_dir)),
                          "response_file": None, "url": url}
    _save(request_path, record)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "pro-roof-layout/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read()
            record.update(http_status=response.status, final_url=response.url,
                          retrieved_at_utc=_now(), content_type=response.headers.get("Content-Type"))
        raw_path.write_bytes(body)
        face["provenance"]["response_file"] = str(raw_path.relative_to(output_dir))
        _save(request_path, record)
    except HTTPError as exc:
        with exc:
            raw_path.write_bytes(exc.read())
        face["provenance"]["response_file"] = str(raw_path.relative_to(output_dir))
        record.update(http_status=exc.code, retrieved_at_utc=_now(), error=str(exc))
        _save(request_path, record)
        raise RuntimeError(f"PVGIS HTTP {exc.code}；原始错误已保存至 {raw_path.name}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        record.update(retrieved_at_utc=_now(), error=str(exc))
        _save(request_path, record)
        raise RuntimeError(f"PVGIS 请求失败：{exc}") from exc
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("PVGIS 返回的内容不是有效 JSON；原始响应已保留") from exc
    return payload, {"request_file": str(request_path.relative_to(output_dir)),
                     "response_file": str(raw_path.relative_to(output_dir)), **record}


def _pvgis(project, source_face, face, energy, output_dir, index):
    location = project.get("location")
    if not isinstance(location, dict):
        raise ValueError("PVGIS 需要 location.latitude 和 location.longitude")
    lat = _number(location.get("latitude"), "纬度", -90, 90)
    lon = _number(location.get("longitude"), "经度", -180, 180)
    tilt = _number(source_face.get("tilt_deg"), "屋面倾角", 0, 90)
    if tilt <= 12:
        raise ValueError("Pro 屋面倾角必须严格大于12°")
    azimuth = _number(source_face.get("azimuth_deg"), "真北顺时针方位角", 0, 360) % 360
    aspect = azimuth - 180  # PVGIS: south 0, west +90, east -90, north -180.
    face.update(tilt_deg=tilt, azimuth_deg=azimuth, pvgis_aspect_deg=aspect)
    params = {"lat": lat, "lon": lon, "peakpower": face["power_kwp"],
              "loss": 0, "pvtechchoice": "crystSi",
              "mountingplace": "building", "angle": tilt, "aspect": aspect,
              "fixed": 1, "optimalinclination": 0, "optimalangles": 0,
              "usehorizon": 1, "outputformat": "json", "browser": 0}
    payload, provenance = _fetch(params, output_dir, index, face)
    face["provenance"] = provenance
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get("inputs"), dict):
            raise ValueError("PVGIS 响应不是预期对象或缺少输入元数据")
        source_loss = _number(payload['inputs'].get('pv_module', {}).get('system_loss'), 'PVGIS返回的系统损耗', 0, 100)
        if source_loss != 0:
            raise ValueError("PVGIS返回的基准已扣系统损耗，不能重复乘0.88；本技能要求loss=0的原始响应")
        rows = payload["outputs"]["monthly"]["fixed"]
        annual = _number(payload["outputs"]["totals"]["fixed"]["E_y"], "PVGIS E_y")
        if len(rows) != 12 or sorted(row["month"] for row in rows) != list(range(1, 13)):
            raise ValueError("PVGIS 月结果必须覆盖不重复的1至12月")
        rows = sorted(rows, key=lambda row: row["month"])
        values = [_number(row["E_m"], "PVGIS E_m") for row in rows]
        if abs(sum(values) - annual) > max(0.12, annual * 0.002):
            raise ValueError("PVGIS 月度合计与年量不一致，停止采用此响应")
    except (KeyError, TypeError) as exc:
        raise ValueError("PVGIS 响应缺少完整的月度/年度固定屋面结果") from exc
    factor = SYSTEM_EFFICIENCY * (1 - energy["additional_shading_loss_pct"] / 100)
    annual_cents = _cents(annual * factor)
    face.update(status="complete", annual_kwh=annual_cents / 100, monthly_kwh=_allocate_months(annual_cents, values),
                source_annual_kwh=annual, source_monthly_sum_kwh=round(sum(values), 6),
                baseline_annual_kwh=annual, system_efficiency=SYSTEM_EFFICIENCY,
                source_system_loss_pct=source_loss,
                radiation_metadata=payload.get("inputs", {}).get("meteo_data", {}),
                system_loss_applied=True)
    if annual == 0:
        face["warnings"].append("PVGIS 对正装机容量返回零发电量；已保留原始值，需复核地点及源数据。")
    if factor == 0:
        face["warnings"].append("额外遮挡损失设为100%，因此估算发电量为零。")


def _specific_yield(face, energy):
    if energy.get("specific_yield_basis") != "before_system_losses":
        raise ValueError("specific_yield 必须声明 specific_yield_basis=before_system_losses；已扣损耗的净值须先按已知来源效率换算，不能重复乘0.88")
    value = _number(energy.get("annual_specific_yield_kwh_kwp"), "未扣系统损耗的年比发电量")
    source = energy.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("specific_yield 必须提供 source；演示值须在 source 中明确写为演示假设")
    baseline = face["power_kwp"] * value
    annual_cents = _cents(baseline * SYSTEM_EFFICIENCY * (1 - energy["additional_shading_loss_pct"] / 100))
    months = None
    if energy.get("monthly_fractions") is not None:
        fractions = energy["monthly_fractions"]
        if not isinstance(fractions, list) or len(fractions) != 12:
            raise ValueError("monthly_fractions 必须含1至12月的12个比例")
        fractions = [_number(v, "月比例", 0, 1) for v in fractions]
        if not math.isclose(sum(fractions), 1, rel_tol=0, abs_tol=1e-6):
            raise ValueError("monthly_fractions 之和必须为1，不自动构造季节分布")
        months = _allocate_months(annual_cents, fractions)
    face.update(status="complete", annual_kwh=annual_cents / 100, monthly_kwh=months,
                annual_specific_yield_kwh_kwp=value, source=source.strip(), system_loss_applied=True,
                baseline_annual_kwh=baseline, system_efficiency=SYSTEM_EFFICIENCY)
    face["warnings"].append("基准年比发电量未扣系统综合损耗，统一乘0.88一次；此方式不自动按各坡倾角和朝向修正。")
    if months is None:
        face["warnings"].append("未提供有来源的月分布，仅输出年量。")
    if value == 0:
        face["warnings"].append("输入基准年比发电量为零；作为显式输入保留，需核对来源。")


def estimate(project, layout, output_dir):
    """Return a dict and write energy.json. Failed estimates remain null, never zero."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {"schema_version": 2, "created_at_utc": _now(), "status": "failed",
              "tile_power_w": TILE_POWER_W, "faces": [], "totals": None, "errors": [],
              "limitations": list(LIMITATIONS), "sources": []}
    try:
        if not isinstance(project, dict) or not isinstance(project.get("energy", {}), dict):
            raise ValueError("project 和 project.energy 必须是对象")
        energy = dict(project.get("energy", {}))
        method = energy.get("method", "none")
        if method not in ("pvgis", "specific_yield", "none"):
            raise ValueError("energy.method 仅支持 pvgis、specific_yield 或 none")
        result.update(method=method, faces=_faces(layout))
        efficiency = _number(energy.get("system_efficiency", SYSTEM_EFFICIENCY), "系统效率", 0, 1)
        if not math.isclose(efficiency, SYSTEM_EFFICIENCY, abs_tol=1e-9):
            raise ValueError("美学光伏瓦Pro屋面排布统一采用系统效率0.88")
        if "system_loss_pct" in energy and not math.isclose(_number(energy["system_loss_pct"], "系统损失百分数", 0, 100), 12, abs_tol=1e-9):
            raise ValueError("system_loss_pct 与0.88系统效率不一致；请移除旧14%损耗，不能叠加扣减")
        energy["additional_shading_loss_pct"] = _number(energy.get("additional_shading_loss_pct", 0), "额外遮挡损失百分数", 0, 100)
        result["assumptions"] = {"system_efficiency": SYSTEM_EFFICIENCY, "system_loss_pct": 12,
                                 "pvgis_loss_pct": 0 if method == "pvgis" else None,
                                 "additional_shading_loss_pct": energy["additional_shading_loss_pct"],
                                 "system_loss_applied": method in ("pvgis", "specific_yield"),
                                 "formula": "E = baseline_annual_kwh × 0.88 × (1 − additional_shading_loss_pct / 100)",
                                 "specific_yield_basis": energy.get("specific_yield_basis") if method == "specific_yield" else None}
        if method == "pvgis":
            result['sources'] = [DOCS, MANUAL]
            result["limitations"] += ["PVGIS 使用通用晶硅及建筑集成温度模型；规格书温度系数和NOCT未另行叠加。",
                                      "PVGIS地形地平线不包含现场树木、烟囱或邻楼细节；额外遮挡比例为用户给定简化值。",
                                      "用户确认系统效率0.88替换旧14%损耗：PVGIS请求loss=0，基准发电量在本地乘0.88一次。保留PVGIS自身温度/弱光模型，不额外叠加14%系统损耗。",
                                      "月量按源月分布分配折算年量，并做分位舍入平衡；年量与12个月合计一致。"]
        for index, (source_face, face) in enumerate(zip(layout["faces"], result["faces"])):
            if face["pv_tiles"] == 0:
                face.update(status="no_pv", annual_kwh=0, monthly_kwh=_monthly([0] * 12))
                continue
            if method == "none":
                face["status"] = "not_requested"
                continue
            try:
                if method == "pvgis":
                    _pvgis(project, source_face, face, energy, output_dir, index)
                else:
                    _specific_yield(face, energy)
            except (ValueError, RuntimeError) as exc:
                error = {"face_id": face["id"], "code": "REQUEST_FAILED" if isinstance(exc, RuntimeError) else "INVALID_INPUT_OR_RESPONSE", "message": str(exc)}
                face.update(status="failed", error=error)
                result["errors"].append(error)
        faces = result["faces"]
        count = sum(f["pv_tiles"] for f in faces)
        complete = all(f["annual_kwh"] is not None for f in faces)
        monthly_complete = complete and all(f["monthly_kwh"] is not None for f in faces)
        annual_cents = sum(_cents(f["annual_kwh"]) for f in faces if f["annual_kwh"] is not None)
        monthly_cents = [sum(_cents(f["monthly_kwh"][i]["energy_kwh"]) for f in faces) for i in range(12)] if monthly_complete else None
        result["totals"] = {"pv_tiles": count, "power_kwp": count * TILE_POWER_W / 1000,
                            "annual_kwh": annual_cents / 100 if complete else None,
                            "monthly_kwh": _monthly(monthly_cents) if monthly_complete else None,
                            "successful_subtotal_annual_kwh": annual_cents / 100,
                            "failed_faces": [f["id"] for f in faces if f["status"] == "failed"]}
        result["status"] = ("no_pv" if count == 0 else "not_requested" if method == "none" else
                            "complete" if complete else "partial" if any(f["status"] == "complete" for f in faces) else "failed")
    except ValueError as exc:
        result["errors"].append({"code": "INVALID_INPUT", "message": str(exc)})
    _save(output_dir / "energy.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--layout", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="输出目录")
    args = parser.parse_args()
    try:
        project = json.loads(args.project.read_text(encoding="utf-8"))
        layout = json.loads(args.layout.read_text(encoding="utf-8"))
        result = estimate(project, layout, args.output)
    except (OSError, ValueError) as exc:
        print(f"无法读取输入或保存结果：{exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "totals": result["totals"], "errors": result["errors"],
                      "output": str(args.output / "energy.json")}, ensure_ascii=False))
    return 1 if result["status"] in ("failed", "partial") else 0


if __name__ == "__main__":
    sys.exit(main())
