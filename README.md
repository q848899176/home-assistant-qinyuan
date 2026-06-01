# Qinyuan Smart Water Purifier for Home Assistant

沁园智联净水器的 Home Assistant 自定义集成。通过沁园云端接口自动登录、发现账号下设备，并创建滤芯剩余寿命传感器。

## 功能

- 通过 Home Assistant 图形界面输入沁园智联手机号和密码
- 自动获取沁园云端 token，无需手动抓包
- 自动发现账号下净水器设备
- 为每台设备创建滤芯寿命百分比传感器
- 默认刷新间隔建议为 3600 秒，可在配置项里调整

## HACS 安装

1. 打开 HACS。
2. 右上角菜单选择“自定义存储库”。
3. 添加仓库地址：`https://github.com/q848899176/home-assistant-qinyuan`
4. 类型选择 `Integration`。
5. 安装后重启 Home Assistant。
6. 进入“设置” -> “设备与服务” -> “添加集成”，搜索 `Qinyuan` 或 `沁园`。

## 手动安装

复制 `custom_components/qinyuan` 到 Home Assistant 的 `custom_components/qinyuan`，然后重启 Home Assistant。

## 配置

在 Home Assistant 集成页面中填写：

- 手机号：沁园智联账号手机号
- 密码：沁园智联账号密码
- 刷新间隔：默认 `3600` 秒

集成会把密码转换为沁园 App 使用的 MD5 大写摘要后保存到 Home Assistant 的本地配置存储中，云端 token 只在运行时保存在内存里。

## 已知说明

沁园官方没有公开文档，接口来自实际 App 行为验证。不同产品型号的滤芯接口可能存在差异，欢迎提交 issue 补充设备型号和日志。

## 隐私

本仓库不包含任何个人手机号、密码、token、Home Assistant 地址、抓包文件或设备私有标识。请不要在 issue 中直接粘贴未脱敏的账号、token 或完整抓包内容。
