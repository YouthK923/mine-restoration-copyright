# 自然恢复软著
历史遗留废弃矿山自然恢复适宜性评价系统 V1.0 —— 计算机软件著作权登记项目

## 目录结构

根目录只保留系统本体与启动所需文件，其余按用途分类：

```
run.py                  启动入口
启动.bat                Windows 一键启动（载入演示数据 + 启动服务）
requirements.txt        依赖清单
seed_demo.py            内置玉田县案例与论文表 1 的标准库（幂等，不动用户数据）
app/                    应用代码（详见下方「系统代码结构」）

文档/                   ★ 项目文档（Markdown 为源文件，docx 为送阅版本）
    软著功能计划.md / .docx
    制作步骤与分工.md / .docx
    演示脚本.md / .docx
    软著登记申请材料形式要求_联网核实报告.md

工具/                   ★ 材料生成与校验脚本
    make_source_doc.py          生成源程序鉴别材料 PDF
    make_manual.py              生成软件说明书 PDF
    make_screenshots.py         自动抓取界面截图（Chrome 无头模式）
    check_materials.py          申请材料形式要求自检（21 项）
    verify_all.py               项目最终验收汇总
    提取论文与模板文本.py        从论文/模板 PDF 提取全文到 参考资料/论文与模板解析文本/
    生成Word中文模板.py         生成 pandoc 中文排版模板
    修正Word标题配色.py         修正 docx 标题样式为「黑体 + 纯黑」
    数值核对/                   案例数值的独立复算脚本

测试/                   ★ 自检脚本（10 套，均从仓库根运行）
    test_ahp.py test_evaluate.py test_web_ahp.py test_web_modules.py
    test_web_evaluate.py test_web_report.py test_ui_fixes.py
    test_new_features.py test_workflow.py test_weights.py

验证数据/               ★ 系统正确性验证数据（8 个带手算期望值的算例）
    README.md                   算例说明、手算过程、期望值对照表、手动核对步骤
    用例01_... .csv …           可直接批量导入的指标数据
    由 工具/数值核对/验证用例.py 生成，与脚本里的期望值同源

软著材料/               ★ 登记提交材料（由工具生成）
    源程序_....pdf / 源程序_提交版（前30页+后30页）_....pdf
    说明书_....pdf
    登记信息表底稿.md
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
seed_demo.py              内置玉田县案例 + 论文表1的 11 项标准与 32 条规则
```

## 启动

```bash
pip install -r requirements.txt
python seed_demo.py     # 载入演示案例（含管理员 admin/admin123）
python run.py           # 打开 http://127.0.0.1:5000
```

Windows 下也可直接双击 `启动.bat`。`seed_demo.py` 是**幂等**的：
演示案例已存在则跳过，**不会删除你自己建立的项目与图斑**。
需要把演示环境彻底重建时用 `python seed_demo.py --reset`。

## 运行自检

```bash
python 测试/test_workflow.py    # 评价流程门禁、数据保护、重复单元拦截
python 测试/test_weights.py     # AHP 权重生效链路
python 工具/check_materials.py  # 申请材料形式要求自检（21 项）
python 工具/verify_all.py       # 项目最终验收汇总
```

## 验证系统计算是否正确

`验证数据/` 里有 8 个算例，期望值全部先用论文公式**手工推算**再与系统比对，
详见 `验证数据/README.md`。

```bash
python 工具/数值核对/验证用例.py          # 建算例 → 跑评价 → 比对期望值
python 工具/数值核对/验证用例.py --clean  # 删除算例
```

覆盖：理想上限、理论下限、面积加权、重金属污染、不适用指标被忽略、
坡度 25° 分界与坡向赋值、等级边界、限制性条件一票否决。

> 算例会保留在系统中供浏览，**生成软著材料前请先 `--clean`**，
> 否则列表页截图会带上这些验证数据。

## 材料生成

```bash
python 工具/make_screenshots.py    # 1) 自动截图（Chrome 无头模式，需先 seed_demo.py）
python 工具/make_manual.py         # 2) 生成说明书 PDF
python 工具/make_source_doc.py     # 3) 生成源程序 PDF
```

- **源程序**：A4 纵向、页眉为软件名称与版本号、页码右上角、每页固定 50 行、
  去除空行保证每页均为有效代码行、末页为程序结束页。超过 60 页时同时生成
  「前 30 页 + 后 30 页」的提交版。
- **说明书**：A4 纵向、页眉同为软件名称与版本号、页码自目录起编号，图文并茂。
- `make_screenshots.py` 以截图模式启动应用（配置项 `SCREENSHOT_MODE`，自动以管理员登录）。
  > 该模式仅为生成配图的开发用途，正常运行时配置为关闭状态。

## 约定

1. **文档以 Markdown 为源文件协作**；需要送阅时用 `工具/生成Word中文模板.py` + pandoc 导出 docx。
2. 已提交的 `文档/软著功能计划.docx` 为对外版本，改动 md 后请同步重新导出。
3. 提交前先拉取远程更新，避免冲突堆积。
4. 提交信息写清做了什么，不要用 "update" 之类的空话。

## 文档导出方式

```bash
# 1) 生成中文排版模板（标题黑体、纯黑）
python 工具/生成Word中文模板.py

# 2) Markdown 转 Word
pandoc "文档/软著功能计划.md" -o "文档/软著功能计划.docx" \
  --reference-doc="<临时目录>/dsh_ref_cn.docx" \
  -f markdown+pipe_tables
```
