# Cruved Tiles layout and Modeling

Almaden 三曲光伏瓦屋面排布与建模技能，调用名称：`$sanqu-roof-layout`。

## 下载与内容

- [技能源码及使用规则](sanqu-roof-layout/SKILL.md)
- [完整安装包 ZIP](sanqu-roof-layout.zip)
- [可运行项目示例](sanqu-roof-layout/references/example-project.json)

包含排布、CAD读写、Blender建模与渲染、发电量计算程序，以及产品网格、品牌标志和4份产品/安装参考PDF。个人Python环境、缓存、历史项目DWG和个人电脑路径不包含在发布包内。

## 固定参数

| 项目 | 当前口径 |
|---|---|
| 型号与功率 | BHAC40R-40，40 W/片 |
| 发电瓦尺寸 | 723×500×41 mm |
| 发电瓦/主配瓦横向有效模数 | 713 mm |
| 沿坡排距 / 挂瓦条间隔 | 405 mm |
| 正脊沿脊有效长度 | 713 mm |
| 最终发电量 | 原估算结果 × 0.88，只应用一次 |

PVGIS气象估算与经验年比发电量两种方式都在原损耗及遮挡计算后额外折减12%；各坡、月量、年量与成功小计统一使用此规则。装机容量仍为完整发电瓦片数×40÷1000 kWp。默认不考虑并网、储能与逆变器选型。

## 安装

下载ZIP并解压，把内部 `sanqu-roof-layout` 文件夹放到 `~/.codex/skills/`。已有同名技能时先保留旧版本，再用此目录更新。

建立本技能专用运行环境：

```sh
python3 ~/.codex/skills/sanqu-roof-layout/scripts/setup.py
```

需要Python 3.11或更新版本；生成三维模型和效果图还需要Blender（已验证5.2版）。DWG导出使用AutoCAD Core Console，当前默认适配macOS AutoCAD 2024；也可直接提供DXF。安装包不包含AutoCAD或Blender软件。

## 调用

提供屋面图纸、业主指定发电区域和项目地点，然后说明：

> 使用 $sanqu-roof-layout，按图中标注区域排布三曲瓦，只铺南坡，输出排布图、3D模型、效果图、功能瓦数量、容量和发电量估算。

图纸由智能体判读并核对单位、北向、坡度、洞口和边界，再整理成项目JSON。关键尺寸不明确时先确认，不把任意DWG直接当成已确认屋面。

也可以直接运行示例（所有尺寸及坐标均为演示输入）：

```sh
~/.codex/skills/sanqu-roof-layout/.venv/bin/python \
  ~/.codex/skills/sanqu-roof-layout/scripts/run_project.py \
  --project ~/.codex/skills/sanqu-roof-layout/references/example-project.json \
  --output ./outputs/example-v1 --render
```

每次使用新的输出目录。可通过 `--blender /实际路径/Blender` 指定程序；省略 `--render` 可先比较排布和容量。

## 输出与核验

输出SVG/DXF总平面及坡面展开图、CSV功能瓦与容量表、可编辑Blender模型、两张PNG效果图、独立HTML报告，以及可追溯的排布和发电量JSON。月年值按0.01 kWh平衡舍入，报告已包含0.88系数，不能再次相乘。

本目录程序通过9项排布/报告测试和18项能耗测试；既有模型流程已验证双坡与带天窗凹形屋面。发电量为方案级近似，部分收口截面为教学表现；实际项目采用其图纸条件和厂家节点资料。

```sh
~/.codex/skills/sanqu-roof-layout/.venv/bin/python ~/.codex/skills/sanqu-roof-layout/scripts/test_layout.py
~/.codex/skills/sanqu-roof-layout/.venv/bin/python ~/.codex/skills/sanqu-roof-layout/scripts/test_energy.py
```
