# 自然恢复软著
历史遗留废弃矿山自然恢复适宜性评价系统 V1.0 —— 计算机软件著作权登记项目

## 目录结构

根目录只保留系统本体与启动所需文件，其余按用途分类：

```
run.py                  启动入口（--no-browser / --port / --dev）
启动.bat                Windows 一键启动（载入演示数据 + 启动服务 + 开浏览器）
创建桌面快捷方式.bat    在桌面与开始菜单创建快捷方式（双击即可）
requirements.txt        依赖清单
seed_demo.py            内置玉田县案例与论文表 1 的标准库（幂等，不动用户数据）
app/                    应用代码（详见下方「系统代码结构」）

文档/                   ★ 项目文档（Markdown 为源文件，docx 为送阅版本）
    软著功能计划.md / .docx
    制作步骤与分工.md / .docx
    演示脚本.md / .docx
    开发日志.md / .docx         ★ 每一次改动的人话版记录，改完代码就来这里补一条
    软著登记申请材料形式要求_联网核实报告.md / .docx

工具/                   ★ 材料生成与校验脚本
    make_source_doc.py          生成源程序鉴别材料 PDF
    make_manual.py              生成软件说明书 PDF（正文内容的唯一来源）
    make_manual_docx.py         按同一份正文生成说明书 Word 版
    make_screenshots.py         自动抓取界面截图（Chrome 无头模式）
    check_materials.py          申请材料形式要求自检（22 项）
    verify_all.py               项目最终验收汇总（含「跑完自检库里不许有孤儿行」检查）
    清理孤儿数据.py             清掉挂在已删除图斑/单元下的残留数据（默认只统计）
    生成图标.py                 生成 app/static/favicon.ico（网页图标 + 快捷方式图标）
    生成登录徽标.py             生成 app/templates/_login_badge.svg（登录页系统徽标）
    创建桌面快捷方式.py         在桌面/开始菜单创建快捷方式
    提取论文与模板文本.py        从论文/模板 PDF 提取全文到 参考资料/论文与模板解析文本/
    生成Word中文模板.py         生成 pandoc 中文排版模板
    生成文档Word.py             把 文档/ 与 软著材料/ 下的 Markdown 批量转成 docx
    修正Word标题配色.py         修正 docx 标题样式为「黑体 + 纯黑」
    数值核对/                   案例数值的独立复算与正确性验证脚本
    界面核对/                   界面行为、文档用词的自检脚本

测试/                   ★ 自检脚本（19 套，均从仓库根运行）
    test_ahp.py test_evaluate.py test_web_ahp.py test_web_modules.py
    test_web_evaluate.py test_web_report.py test_ui_fixes.py
    test_new_features.py test_workflow.py test_weights.py
    test_profile.py test_register.py test_login.py test_timefmt.py
    test_delete_cascade.py test_unit_config.py test_robustness.py
    test_standard_check.py
    test_edge_cases.py       ★ 边界与健壮性专项（数值/输入/门禁/安全/导入/空库）

验证数据/               ★ 系统正确性验证数据（8 个带手算期望值的算例）
    使用说明.md                 ★ 使用文档：两种核对方式、逐步操作、常见问题
    算例与手算过程.md           每个算例的详细手算推导、公式、论文表 3 权重
    README.md                   文件夹索引
    用例01_... .csv …           可直接批量导入的指标数据
    由 工具/数值核对/验证用例.py 生成，与脚本里的期望值同源

软著材料/               ★ 登记提交材料（由工具生成）
    源程序_....pdf / 源程序_提交版（前30页+后30页）_....pdf
    说明书_....pdf / 说明书_....docx   （提交用 PDF，Word 版供改字，两版同源）
    登记信息表底稿.md / .docx
    截图/                       界面截图

参考资料/               ★ 只读参考件（不纳入版本控制）
    论文原稿.docx               论文初稿
    论文全文文本.md             论文全文纯文本，便于检索
    同类软著样例/               两份他人软著的源代码与说明书，作格式模板
    论文与模板解析文本/         上述文件的文本提取结果
```

## 获取参考资料（新成员必读）

`参考资料/` 下的三个大体积二进制文件**不在仓库中**（避免仓库膨胀），
请从项目共享盘获取后按上表位置放入：

- `参考资料/同类软著样例/` —— 软著材料格式模板 A（变压器项目说明书、代码）与
  格式模板 B（电网项目用户手册、源代码，60 页源程序排版范式）
- `参考资料/论文原稿.docx` —— 论文初稿

> 这些是**只读参考件**，不参与协作编辑，因此不需要版本控制。
> `参考资料/论文全文文本.md` 已入库，检索论文内容时用它比读 PDF 方便。

## 系统代码结构

```
run.py                    启动入口
app/
├── config.py             配置
├── models.py             数据模型（16 张表）
├── forms.py              表单定义
├── utils/constants.py    论文全部算法常量（理想极值、RI、坡向赋值、表3权重）
│       schema.py         轻量结构迁移（为已有库补列）
│       uploads.py        上传文件处理
│       charts.py         纯 SVG 图表（单色可打印）
│       browser.py        HTML 转 PDF（浏览器无头打印）
├── services/             ahp_service（AHP 权重引擎）
│                         standardization（四类标准化）
│                         weight_service（权重方案存取与生效）
│                         evaluation_service（分单元赋分/面积加权/等级判定）
│                         workflow（评价流程前置条件）
│                         indicator_service / import_service
│                         report_service（Word 报告生成）
│                         audit（操作审计）
├── views/                auth/project/unit/standard/constraint
│                         ahp/indicator/evaluate/report
└── templates/            各功能页面模板
seed_demo.py              内置示例案例 + 内置标准库的 12 项标准与 37 条规则
```

## 启动

**最省事：在桌面放一个快捷方式，以后双击就能用。**

```bash
python 工具/创建桌面快捷方式.py       # 在桌面和开始菜单创建快捷方式
```

（Windows 下也可以直接双击根目录的 `创建桌面快捷方式.bat`。）

不想建快捷方式时，**直接双击根目录的 `启动.bat`** 也可以：它会自动找 Python、
检查并安装依赖、写入演示数据、启动服务并打开浏览器。给别人拷源码时，
把 `启动.bat` 与 `工具/离线依赖.py` 生成的 `offline_wheels/` 一起带上，
**对方没有网络也能把依赖装上**：

```bash
python 工具/离线依赖.py              # 把依赖的 wheel 下载到 offline_wheels/
```

之后**双击桌面上的「启动」图标**即可：服务启动、浏览器自动打开、直接进登录页。
演示账号 `admin` / `admin123`。

> - 桌面图标叫「启动」，开始菜单里用软件全称，方便按关键词搜索到。
> - 换个名字：`python 工具/创建桌面快捷方式.py --name 矿山适宜性评价`，
>   或直接在桌面上右键图标 → 重命名。
> - 图标取自 `app/static/favicon.ico`，与网页标签页图标是同一个。
> - 服务已在运行时再次双击，只会打开浏览器，不会重复启动。
> - 停止系统：在黑色命令行窗口按 `Ctrl+C`，或直接关掉那个窗口。
> - 移动或重命名了项目文件夹后，快捷方式会失效，重新运行一次创建脚本即可。
> - 删除快捷方式：`python 工具/创建桌面快捷方式.py --remove`

### 其他启动方式

```bash
python seed_demo.py     # 载入演示案例（含管理员 admin/admin123）
python run.py           # 启动并自动打开浏览器
```

`run.py` 的可用参数：

```bash
python run.py --no-browser   # 只启动服务，不打开浏览器
python run.py --port 5001    # 换端口（默认 5000）
python run.py --dev          # 开发模式：开启热重载与调试器
```

> `seed_demo.py` 是**幂等**的：演示案例已存在则跳过，
> **不会删除你自己建立的项目与图斑**。需要把演示环境彻底重建时用
> `python seed_demo.py --reset`。

## 运行自检

```bash
python 测试/test_workflow.py    # 评价流程门禁、数据保护、重复单元拦截
python 测试/test_weights.py     # AHP 权重生效链路
python 测试/test_timefmt.py     # 时间显示：库里存 UTC、页面显示本地时间
python 工具/check_materials.py  # 申请材料形式要求自检（22 项）
python 工具/verify_all.py       # 项目最终验收汇总
```

## 验证系统计算是否正确

`验证数据/` 里有 8 个算例，期望值全部先用论文公式**手工推算**再与系统比对。

📖 **详细用法见 [`验证数据/使用说明.md`](验证数据/使用说明.md)**
（两种核对方式、逐步操作、期望值对照表、常见问题）。

```bash
python 工具/数值核对/验证用例.py          # 建算例 → 跑评价 → 比对期望值
python 工具/数值核对/验证用例.py --clean  # 删除算例
```

覆盖：理想上限、理论下限、面积加权、重金属污染、不适用指标被忽略、
坡度 25° 分界与坡向赋值、等级边界、限制性条件一票否决。
除总分外，**每个单元的得分也逐个核对**（总分对不代表每个单元都对，
可能互相抵消）；算例 05/06 另建孪生算例对照。

> 算例会保留在系统中供浏览，**生成软著材料前请先 `--clean`**，
> 否则列表页截图会带上这些验证数据。

## 材料生成

```bash
python 工具/make_screenshots.py    # 1) 自动截图（Chrome 无头模式，需先 seed_demo.py）
python 工具/make_manual.py         # 2) 生成说明书 PDF
python 工具/make_manual_docx.py    # 3) 生成说明书 Word 版（同一份正文）
python 工具/make_source_doc.py     # 4) 生成源程序 PDF
python 工具/生成文档Word.py         # 5) 文档与底稿的 Markdown 转 Word
```

- **源程序**：A4 纵向、页眉为软件名称与版本号、页码右上角、每页固定 50 行、
  去除空行保证每页均为有效代码行、末页为程序结束页。超过 60 页时同时生成
  「前 30 页 + 后 30 页」的提交版。
- **说明书**：A4 纵向、页眉同为软件名称与版本号、页码自目录起编号，图文并茂。
  **提交用 PDF**；`make_manual_docx.py` 另出一份 Word 版（正文、目录、截图与 PDF
  同源，页数也一致），供项目成员直接改字、写批注，**不作为提交形式**。
- `make_screenshots.py` 以截图模式启动应用（配置项 `SCREENSHOT_MODE`，自动以管理员登录）。
  > 该模式仅为生成配图的开发用途，正常运行时配置为关闭状态。

## 约定

1. **每改一次就在 `文档/开发日志.md` 里补一条**，写清「做了什么 / 为什么 / 影响哪些文件 / 怎么验证的」。
   `git log` 只记录改了什么文件，说明不了动机；日志是给人看的版本。
2. **文档以 Markdown 为源文件协作**；需要送阅时用 `工具/生成文档Word.py` 批量导出 docx。
3. 已提交的 `文档/*.docx` 为对外版本，改动 md 后请同步重新导出。
4. 提交前先拉取远程更新，避免冲突堆积。
5. 提交信息写清做了什么，不要用 "update" 之类的空话。
6. **临时脚本不要留在仓库里**：名字以 `_` 开头的辅助脚本已被 `.git/info/exclude` 忽略，
   用完请删除，不要提交。

## 文档导出方式

```bash
# 一键把 文档/ 下所有 md 转成 docx（内部会先生成中文排版模板）
python 工具/生成文档Word.py
```

单篇转换：

```bash
# 1) 生成中文排版模板（标题黑体、纯黑）
python 工具/生成Word中文模板.py

# 2) Markdown 转 Word
pandoc "文档/软著功能计划.md" -o "文档/软著功能计划.docx" \
  --reference-doc="<临时目录>/dsh_ref_cn.docx" \
  -f markdown+pipe_tables
```
