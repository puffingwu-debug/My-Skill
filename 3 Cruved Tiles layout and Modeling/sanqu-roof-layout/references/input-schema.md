# 输入 project.json

由智能体读图后整理，用户无需手写。example-project.json是可运行演示，不能直接当真实项目。

## 顶层

- project_name、geometry_source：名称与来源图纸/版本/图层/尺寸依据。
- units必须"m"。图纸毫米先换算，屋面boundary长度必须是坡面展开实长。
- lateral_pitch_m=0.713，course_pitch_m=0.405，power_w=40：已确认。
- faces：独立坡面数组；edges：共享收口边数组（正脊只出现一次）。
- fittings：如 {"name":"正脊封头","count":2,"source":"R1两个端点"}。
- spare_pct：另加备料百分比，默认0，不计装机。
- assumptions：项目条件/未核实事项字符串数组。
- location：latitude/longitude/label。energy详见energy-method.md。2026-09-14用户确认最终发电量统一乘0.88，由程序在原系统损耗与额外遮挡后应用一次；无需在项目输入中重复扣减源年比发电量或增加12%遮挡/系统损耗。

## 每坡示例

```json
{"id":"S1","name":"南坡","origin":[0,0,3],"tilt_deg":30,"azimuth_deg":180,
 "boundary":[[0,0],[8.4,0],[8.4,4.55],[0,4.55]],
 "pv_regions":[[[0.3,0],[8.1,0],[8.1,4.3],[0.3,4.3]]],
 "grid_origin":[0,0],
 "obstacles":[{"id":"SKY1","type":"skylight","polygon":[[3.6,1.9],[4.8,1.9],[4.8,2.65],[3.6,2.65]],"clearance_m":0.15}]}
```

世界坐标X东、Y北、Z上；origin是本坡局部(0,0)的真实三维坐标。局部Y从檐向脊；X为坡外看上坡时的右方，南坡朝东、北坡朝西。tilt_deg对水平倾角；azimuth_deg为真北0°顺时针，东90、南180、西270。程序据此生成右手正交u/v/normal，不能另外给与朝向矛盾的随意旋转基底。多坡共享脊顶必须在同一世界坐标处相接。

boundary支持凹多边形但不可自交。holes可另外给孔洞多边形数组。obstacles会挖孔，clearance只扩大发电禁布带，洞口周边保留配瓦。预留带按图纸输入，不沿用示例。

pv_regions必须明确，[]表示全坡配瓦；可以多个不相连区域。只有原片完整足迹在指定区且避开洞口/留带才放发电瓦，否则该格用可裁配瓦。不会自动选择北坡发电。

grid_origin为首个模数左下角，默认boundary最小X/Y。原片从格左下角起宽723或724、长500 mm；横713纵405重复。可以根据业主外观/容量要求改起排位置比较方案，脚本不自动寻找全局最优。

min_companion_area_m2默认0.0001用于剔除极小计算碎片，不是现场最小可裁尺寸。实际细窄件可安装性需要回看节点。

## 收口边

```json
{"id":"R1","type":"ridge","start":[0,3.94,5.275],"end":[8.4,3.94,5.275]}
```

start/end世界三维坐标，沿边实长；type为ridge正脊、hip斜脊、verge封檐/山墙边、valley沟瓦、eave檐口。檐口未有现款有效尺寸仅列延米。折边分段后核对搭接节点；同一公共脊不能重复。未输入的边不能解读为不需收口，项目说明必须说明节点清单是否完整。异型封头等用fittings。

## 输出

run_project.py --project <JSON> --output <新目录> --render；去掉--render可以快速对比排布。非空目录拒绝写入，改V2保留旧稿。

layout.json是2D/3D/统计共同源。瓦片有稳定面号行列ID、kind、footprint原片足迹、parts裁边后的outer/holes、center原片中心。parts只供模型显示，不输出裁切统计。summary.capacity_kwp不含备料。模型/图像必须从本版本layout生成，不能混用旧文件。

energy.json的`assumptions.generation_factor=0.88`、`faces[].generation_factor=0.88`表示最终发电量已经折减；`faces[].before_generation_factor`保留基础月/年量。最终月/年以0.01 kWh按最大余数平衡舍入，全屋总量与成功小计累加已折减的坡面值；报告直接使用这些输出并注明已应用0.88，不能再次乘。源气象响应、源年比发电量、40 W/片、瓦数量及装机容量不变。
