# 简单发电量估算

本技能只估算装机容量与发电量，不涉及并网方案、储能、逆变器选型或经济收益。现款三曲瓦按 **40 W/片**；只统计 `layout.faces[].tiles` 中 `kind: "pv"`，不从屋面总面积反推容量，不把配瓦算作发电瓦，也不重复乘屋面数量。

入口：`scripts/estimate_energy.py`；函数 `estimate(project, layout, output_dir) -> dict`，同时写出 `output_dir/energy.json`。

**2026-09-14用户确认：统一最终发电量系数为0.88，即在原估算结果上额外折减12%。** PVGIS和经验净年比发电量两种方法，都在原系统损耗及额外遮挡处理后，由程序在汇总前逐坡乘一次。逐坡/月/年、全屋汇总和成功坡面小计均适用；瓦片数量、40 W额定功率和装机容量不变。原始气象响应、源年比发电量不改写。

输出以 `assumptions.generation_factor=0.88` 和 `face.generation_factor=0.88` 标识已应用；`face.before_generation_factor` 保留折减前的基础月量/年量。最终报告应注明“发电量已应用0.88系数”，**不能对输出再乘一次，也不能把0.88重复并入系统损耗或额外遮挡参数**。

```sh
python3 scripts/estimate_energy.py --project project.json --layout layout.json --output output
```

## 输入

```json
{
  "location": {"latitude": 31.78, "longitude": 119.97, "label": "联网自测坐标，非项目定位"},
  "energy": {
    "method": "pvgis",
    "system_loss_pct": 14,
    "additional_shading_loss_pct": 0
  }
}
```

每个屋面应有唯一字符串 `id`、`name`、`tilt_deg`、`azimuth_deg` 和 `tiles`。倾角从水平面算起，范围0–90°。方位角以**真北0°、东90°、南180°、西270°**，接受0–360°。有发电瓦的PVGIS屋面必须填写倾角与方位，不根据未标北向的截图猜测。没有发电瓦的屋面不请求气象接口。

`energy.method` 只接受 `pvgis`、`specific_yield`、`none`；未填时视为 `none`，不得自行改为经验发电量。

## PVGIS 气候平均估算

使用欧盟JRC官方的 `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`，逐坡传入真实装机kWp、`pvtechchoice=crystSi`、`mountingplace=building`、屋面倾角和固定朝向。PVGIS的方位规则是南0°、西+90°、东−90°，因此程序转换为 `aspect = (azimuth_deg % 360) - 180`。不启用最佳倾角或自动朝向，否则会覆盖实际屋面条件。[官方API参数](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en)

不强制选择辐照数据库，由PVGIS按坐标选择，再从原始响应保存实际数据库与年份。官方5.3资料给出的SARAH3/ERA5历史时段为2005–2023；SARAH3与ERA5各有覆盖区域，不能把某个数据库当作任意地点都可用。ERA5用于卫星数据库未覆盖的区域。覆盖和可用性以请求实际响应为准；不因某个地点失败而移动坐标或替换成另一个城市。[官方数据版本说明](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5_en)、[用户手册的数据库说明](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)

PVGIS启用地形地平线 `usehorizon=1`。这不能代替树木、烟囱、天窗或邻楼的现场遮挡分析。`additional_shading_loss_pct` 是额外的统一折减假设，0表示本次未追加该项，不表示已确认现场无遮挡。[PVGIS用户手册](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)

计算关系：

- 屋面装机 `P_i = 发电瓦片数_i × 40 / 1000`，单位kWp。
- 基础每月 `E_i,m,基础 = PVGIS每月E_m × (1 − 额外遮挡损失/100)`，单位kWh。
- 最终每月 `E_i,m = E_i,m,基础 × 0.88`；最终每坡年量为基础年量乘0.88。月/年按下述0.01 kWh规则平衡舍入，全屋只相加已折减的坡面结果，不再乘系数。原始PVGIS年量另存，避免接口四舍五入差异丢失来源信息。

`system_loss_pct` 默认14%，属于**明确可改的综合损耗假设**，已经在PVGIS的`loss`参数内扣除，不再重复乘0.86。PVGIS还使用自身的温度/弱光模型，所以不再把规格书Pmax温度系数和NOCT叠加扣一次。

当前没有PAN；采用通用晶硅、建筑集成安装条件近似。三曲瓦按整个屋面的等效倾角处理，**未计算三个曲面的独立受光、局部遮挡、失配、旁路二极管或真实BIPV通风温升**。输出是历史气候条件下的简单平均发电量，不是指定未来年份的保证值，也不能称为本组件精确仿真。

每个请求在 `energy_raw/` 用独立时间戳文件保存：完整URL与参数、屋面id、UTC请求/接收时间、HTTP状态、原始响应字节。成功结果还保留数据库/年份元数据。HTTP错误正文也保存；网络失败保留错误，不伪造响应，不静默切换到离线经验值。旧文件可能仍在输出目录，只能引用本次 `energy.json` 中有记录的响应文件。

## 有来源的离线年比发电量

仅在显式指定 `method: "specific_yield"` 时使用。必须给出非负 `annual_specific_yield_kwh_kwp` 和非空 `source`。来源可为当地同类项目数据、明确日期/条件的报告，或用户允许的**演示假设**；假设必须在source中明说，不得伪称实测。

```json
{
  "energy": {
    "method": "specific_yield",
    "annual_specific_yield_kwh_kwp": 1000,
    "source": "演示假设：1000 kWh/kWp/年，仅用于测试；未核验当地气象",
    "system_loss_pct": 14,
    "additional_shading_loss_pct": 0
  }
}
```

这里的年比发电量定义为**已经包含来源系统损耗的净值**：`E_i,年 = P_i × 源净年比发电量 × (1 − 额外遮挡损失/100) × 0.88`。源净年比发电量保持原值；不再次使用`system_loss_pct`扣损耗，结果明确记录 `system_loss_applied: false`，但仍应用统一最终0.88系数。若来源已经包含同一遮挡损耗，应把额外遮挡设为0以免重复扣除。

离线方法不自行按倾角、朝向修正；一个全局比发电量代表此次所有坡面的经验近似。如需分别考虑各坡朝向，优先用PVGIS，不能给不同朝向套用未经说明的精度承诺。

可选 `monthly_fractions` 是按1至12月排序的12个非负比例，和必须为1，来源应与source一起说明。缺少时只输出已乘0.88的年量，月量为`null`，不均分或虚构季节分布。

两种方法均先保留基础月量/年量，再逐坡乘0.88：最终年量保留0.01 kWh，月量按最大余数法分配到0.01 kWh，保证各月非负、月合计等于最终年量。全屋月量、年量和成功小计由这些最终坡面值相加，不另行乘系数；不能各自独立折减汇总量造成二次乘或舍入差异。

## 状态与报告规则

| status | 含义 |
|---|---|
| `complete` | 所有发电坡面计算成功；离线无月分布仍可成功，但月量为null |
| `no_pv` | 全屋没有发电瓦，装机/年量/月量均为0，不请求PVGIS |
| `not_requested` | method为none，有装机数但未请求发电量，年/月量为null |
| `partial` | 部分发电坡面成功、部分失败；全屋年/月量为null |
| `failed` | 所有发电坡面失败或输入结构无效；不能显示为零发电量 |

`totals.successful_subtotal_annual_kwh` 只表示已应用0.88的已知坡面小计，部分失败时**不能作为全屋年发电量**。错误保留在`errors`及对应坡面的`error`中。结构无效时`totals`为null。重复屋面id或同坡重复瓦片id会报错，防止重复累计。

接口返回正装机下的零发电量会保留并附提示，乘0.88后仍为零；零值不同于空值，失败或未请求的`null`不能转成零。核验原始响应时，月度数据必须完整覆盖1至12月、无重复、为有限非负数，并与源年量一致到容许的舍入差异范围；最终月量只与最终年量核对，不能与未折减的源年量直接比较。CLI在failed/partial时返回退出码1，输入文件不可读时返回2；其他状态返回0。

官方文档核验日期：2026-09-13。每次实际估算另存UTC获取时间，不能把本次说明日期当成气象资料年份。
