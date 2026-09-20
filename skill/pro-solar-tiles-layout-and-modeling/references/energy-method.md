# 简单发电量估算

本技能只估算装机容量与发电量，不涉及并网方案、储能、逆变器选型或经济收益。现款Pro 光伏瓦按 **70 W/片**；只统计 `layout.faces[].tiles` 中 `kind: "pv"`，不从屋面总面积反推容量，不把配瓦算作发电瓦，也不重复乘屋面数量。

入口：`scripts/estimate_energy.py`；函数 `estimate(project, layout, output_dir) -> dict`，同时写出 `output_dir/energy.json`。

```sh
python3 scripts/estimate_energy.py --project project.json --layout layout.json --output output
```

## 输入

```json
{
  "location": {"latitude": 31.78, "longitude": 119.97, "label": "联网自测坐标，非项目定位"},
  "energy": {
    "method": "pvgis",
    "system_efficiency": 0.88,
    "additional_shading_loss_pct": 0
  }
}
```

每个屋面应有唯一字符串 `id`、`name`、`tilt_deg`、`azimuth_deg` 和 `tiles`。倾角从水平面算起；Pro 铺设坡度须严格大于12°。方位角以**真北0°、东90°、南180°、西270°**，接受0–360°。有发电瓦的PVGIS屋面必须填写倾角与方位，不根据未标北向的截图猜测。没有发电瓦的屋面不请求气象接口。

`energy.method` 只接受 `pvgis`、`specific_yield`、`none`；未填时视为 `none`，不得自行改为经验发电量。

`energy.system_efficiency` 默认且仅接受 **0.88**，对应12%综合系统损耗。这是用户确认的统一方案计算口径，**替换原14%系统损耗**。兼容旧字段`system_loss_pct`时只接受12；旧14或其他不一致值须改正，不能默默忽略后继续算。结果的`assumptions`明确记录`system_efficiency: 0.88`、`system_loss_pct: 12`；PVGIS方法另记`pvgis_loss_pct: 0`。

统一公式为`E = E₀ × 0.88 × (1 − 额外遮挡损失/100)`，其中`E₀`是**未扣综合系统损耗的基准发电量**，不是已扣损耗的旧结果。月量、年量都采用同一效率且只应用一次；把已折减的月量相加得到年量后，不再乘0.88。

## PVGIS 气候平均估算

使用欧盟JRC官方的 `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc`，逐坡传入真实装机kWp、`pvtechchoice=crystSi`、`mountingplace=building`、`loss=0`、屋面倾角和固定朝向。PVGIS的方位规则是南0°、西+90°、东−90°，因此程序转换为 `aspect = (azimuth_deg % 360) - 180`。不启用最佳倾角或自动朝向，否则会覆盖实际屋面条件。[官方API参数](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en)

不强制选择辐照数据库，由PVGIS按坐标选择，再从原始响应保存实际数据库与年份。各数据库各有覆盖区域与历史时段，不能把某个数据库当作任意地点都可用。覆盖和可用性以请求实际响应为准；不因某个地点失败而移动坐标或替换成另一个城市。[官方数据版本说明](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5_en)、[用户手册的数据库说明](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)

PVGIS启用地形地平线 `usehorizon=1`。这不能代替树木、烟囱、天窗或邻楼的现场遮挡分析。`additional_shading_loss_pct` 是额外的统一折减假设，0表示本次未追加该项，不表示已确认现场无遮挡。[PVGIS用户手册](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)

计算关系：

- 屋面装机 `P_i = 发电瓦片数_i × 70 / 1000`，单位kWp。
- 每月 `E₀_i,m = PVGIS在loss=0时返回的每月E_m`，单位kWh。
- 每月 `E_i,m = E₀_i,m × 0.88 × (1 − 额外遮挡损失/100)`，单位kWh。
- 每坡先以源年量 `E_y × 0.88 × (1 − 额外遮挡损失/100)` 确定折算年量，再按源月量比例分配并平衡0.01 kWh舍入尾差；保证12个月合计等于该年量。全屋按坡相加，原始PVGIS年量和月量均保留。

PVGIS请求中不扣综合系统损耗，回传基准发电量后才在本地应用0.88。不得同时给PVGIS传`loss=12`又在本地乘0.88，也不能在已扣14%的旧结果上直接乘0.88。PVGIS基准仍包含所选气象、倾角、朝向及其温度/弱光模型；`loss=0`不代表所有物理损耗均为零，所以不再把规格书Pmax温度系数和NOCT叠加扣一次。

当前没有PAN；采用通用晶硅、建筑集成安装条件近似。Pro 光伏平瓦按各坡真实倾角处理，**未计算局部遮挡、失配、旁路二极管或真实BIPV通风温升**。输出是历史气候条件下的简单平均发电量，不是指定未来年份的保证值，也不能称为本组件精确仿真。

每个请求在 `energy_raw/` 用独立时间戳文件保存：完整URL与参数、屋面id、UTC请求/接收时间、HTTP状态、原始响应字节。成功结果还保留数据库/年份元数据。HTTP错误正文也保存；网络失败保留错误，不伪造响应，不静默切换到离线经验值。旧文件可能仍在输出目录，只能引用本次 `energy.json` 中有记录的响应文件。

## 有来源的离线年比发电量

仅在显式指定 `method: "specific_yield"` 时使用。必须给出非负 `annual_specific_yield_kwh_kwp`、`specific_yield_basis: "before_system_losses"`和非空`source`。来源应明确数据日期、条件以及未扣综合系统损耗的口径；用户允许的**演示假设**也须在source中明说，不得伪称实测。

```json
{
  "energy": {
    "method": "specific_yield",
    "annual_specific_yield_kwh_kwp": 1000,
    "specific_yield_basis": "before_system_losses",
    "source": "演示假设：未扣综合系统损耗的年比发电量1000 kWh/kWp，仅用于测试；未核验当地气象",
    "system_efficiency": 0.88,
    "additional_shading_loss_pct": 0
  }
}
```

这里的年比发电量只接受**未扣综合系统损耗的基准值**：`E₀_i,年 = P_i × 基准年比发电量`，再按`E_i,年 = E₀_i,年 × 0.88 × (1 − 额外遮挡损失/100)`计算。结果明确记录`system_loss_applied: true`。例如仅作公式校验：1 kWp × 1000 kWh/kWp × 0.88 = 880 kWh。

来源若只有已扣系统损耗的净年比发电量，须先取得来源的系统效率`η_source`，据`基准值 = 来源净值 / η_source`换算并在source记录原值、效率和公式，之后才以`before_system_losses`输入。来源效率不明则列缺资料，不盲乘0.88、不假定来源为旧0.86，也不把净值改名成基准值。若来源已包含同一遮挡损耗，应把额外遮挡设为0以免重复扣除。

离线方法不自行按倾角、朝向修正；一个全局比发电量代表此次所有坡面的经验近似。如需分别考虑各坡朝向，优先用PVGIS，不能给不同朝向套用未经说明的精度承诺。

可选 `monthly_fractions` 是按1至12月排序的12个非负比例，和必须为1，来源应与source一起说明。缺少时只输出年量，月量为`null`，不均分或虚构季节分布。月量由已经应用0.88及额外遮挡后的年量分配，不再二次折减；保留0.01 kWh，不足0.01的小数部分按最大余数顺序分配，保证所有月份非负且月合计与年量一致。

## 状态与报告规则

| status | 含义 |
|---|---|
| `complete` | 所有发电坡面计算成功；离线无月分布仍可成功，但月量为null |
| `no_pv` | 全屋没有发电瓦，装机/年量/月量均为0，不请求PVGIS |
| `not_requested` | method为none，有装机数但未请求发电量，年/月量为null |
| `partial` | 部分发电坡面成功、部分失败；全屋年/月量为null |
| `failed` | 所有发电坡面失败或输入结构无效；不能显示为零发电量 |

`totals.successful_subtotal_annual_kwh` 只表示已知坡面的小计，部分失败时**不能作为全屋年发电量**。错误保留在`errors`及对应坡面的`error`中。结构无效时`totals`为null。重复屋面id或同坡重复瓦片id会报错，防止重复累计。

接口返回正装机下的零发电量会原样保留并附提示；零值不同于空值。月度数据必须完整覆盖1至12月、无重复、为有限非负数，并与源年量一致到容许的舍入差异范围。CLI在failed/partial时返回退出码1，输入文件不可读时返回2；其他状态返回0。

官方API文档核验日期：2026-09-14。每次实际估算另存UTC获取时间，不能把本次说明日期当成气象资料年份。
