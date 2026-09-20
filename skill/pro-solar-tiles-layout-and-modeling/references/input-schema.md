# Pro 项目输入

由智能体读图整理，用户不需手写JSON。示例文件是合成回归样例，实际项目从原图重新取尺寸。

## 顶层

project_name，units="m"，geometry_source记录图名/页码/版本与尺寸依据；power_w=70、lateral_pitch_m=1.220、course_pitch_m=0.340固定。faces为独立铺瓦坡面；edges为不重复的收口线；fittings按明确节点数量列；spare_pct默认0且不计装机；assumptions为来源冲突与方案假设。location/energy见[energy-method.md](energy-method.md)。

energy.system_efficiency默认且仅接受0.88；兼容旧字段system_loss_pct时仅接受等效的12，旧14须改为12或移除，不能与0.88叠乘。PVGIS请求固定loss=0，在本地对基准月/年发电量应用0.88一次。specific_yield方法必须填写specific_yield_basis="before_system_losses"、annual_specific_yield_kwh_kwp及source；未注明口径或已扣损耗的净值不能直接作为输入。

## 每个坡面

```json
{"id":"S1","name":"南坡","coordinate_space":"developed",
 "origin":[0,0,9.7],"tilt_deg":21.8014094864,"azimuth_deg":180,
 "boundary":[[0,0],[10.6,0],[10.6,6.19294],[0,6.19294]],
 "tile_regions":[[[0.065,0],[10.535,0],[10.535,6.19294],[0.065,6.19294]]],
 "pv_regions":[[[0.065,0],[10.535,0],[10.535,6.19294],[0.065,6.19294]]],
 "grid_origin":[0.065,0],"obstacles":[]}
```

这里尺寸只是接口例，不能当未来项目默认值。

boundary须为无自交坡面展开边界；坐标为米，不是图纸水平投影。坡比h/run时倾角atan(h/run)，斜长sqrt(run²+h²)，或者从投影除cos(倾角)；输入已是展开实长时不再换算。tilt_deg必须严格>12°。不默认北针朝上或倾角30°。

世界X东Y北Z上，azimuth_deg为真北0°顺时针（东90、南180、西270）。origin是本坡局部(0,0)真实世界坐标。u横向、v从檐向脊，由tilt/azimuth生成正交基。若把建筑轴线视作近似东西/南北，应在assumptions里明示方位场景，不能冒充实测。

pv_regions为用户指定发电区域，可多个多边形；[]表示全部非发电配瓦。完整1240×390mm足迹都在区域且避开孔洞才成为发电瓦。

tile_regions可选，用来预留收口实际占用区域；省略则全boundary铺瓦。该区域内由完整PV或可裁整/半配瓦覆盖，区域外为收口/支承，不能偷偷当作PV损耗面积。统计保留毛坡面area_m2与铺瓦tile_area_m2。

holes为明确洞口多边形；obstacles每项有id、type、polygon、clearance_m（须有节点依据）；洞口从屋面扣除，clearance只禁PV，允许配瓦与泛水处理。图上无洞口不代表现场无新增物。

grid_origin为整瓦格参考左下角，默认铺瓦范围最小X/Y；奇数索引排整体左移610mm形成错缝。原片实体1240×390mm，半配瓦630×390mm；边部裁后整体能落入630mm宽时用半配瓦，否则用整配瓦。无四分之一规格。边余料不跨格优化。

## 收口与背景

edges每项id、type（ridge/hip/verge/valley/eave/wall）、start/end三维世界坐标、可选face_id/side。仅有证据时填写actual_length_m、effective_length_m与source，才会计算数量；否则按延米列。共享正脊只录一次。

context.objects：{type:"box",label,center:[x,y,z],size:[w,d,h]}；context.roof_faces为非Pro背景坡面，含origin/u/v/normal/boundary；context.wall_panels为高低跨竖面，含世界vertices。背景不进入瓦片计数与装机。

## 共同输出

layout.json为图纸、模型、报告唯一排布源；tiles稳定id，kind=pv/companion，stock_type=full/half，row/col，center与virtual_center，width_m/length_m，footprint完整原片、parts裁边outer/holes，power_w=70或0。virtual_center保留边部半瓦所处的虚拟整瓦网格，用于左右搭接倾斜。容量不得由面积或渲染对象数量反推。
