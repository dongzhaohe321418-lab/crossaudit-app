# CrossAudit Visual Decision System · 视觉决策系统

> 审美不是"会加毛玻璃、渐变和动画"，而是能持续判断：什么重要、什么应该删除、
> 什么程度刚刚好。
>
> Aesthetics is not knowing how to add glass, gradients and motion. It is the
> sustained judgement of what matters, what to delete, and how much is exactly
> enough.

**Status.** This is the governing judgement framework for every CrossAudit
surface — console, website, native shell. `UI_DESIGN_SPEC.md` supplies tokens
and component recipes; *this* document decides what deserves to exist. Where
they conflict, this file wins. Authored by the project owner, 2026-08-12.

---

## 1. 审美立场 · The stance

CrossAudit 的视觉身份：**安静高效，像 Apple 专业软件一样精确，有科学仪器的
可信度，但没有传统企业后台的笨重感。**

Quiet and efficient; precise like Apple's professional software; the
credibility of a scientific instrument; none of the weight of an enterprise
back office.

设计优先级固定，不可重排 · Fixed priority order:

1. 清晰 Clarity
2. 层级 Hierarchy
3. 克制 Restraint
4. 反馈 Feedback
5. 氛围 Atmosphere
6. 装饰 Decoration

**如果装饰损害了前四项，删掉。** If decoration costs any of the first four,
delete the decoration.

## 2. 审美主要体现在删除 · Aesthetics is mostly deletion

低质量页面的特征 · The low-quality signature:

- 每个功能都是一张卡片 every feature its own card
- 所有标题都很大 every heading large
- 到处是渐变、光晕和玻璃 gradients, glows and glass everywhere
- 信息密度平均，没有视觉重点 uniform density, no focal point
- 每个按钮都在争夺注意力 every button competing
- 为了显得丰富而添加无意义文案 filler copy added to look rich

高质量设计主动删除 · High-quality design actively removes:

- 没有决策价值的状态 states with no decision value
- 用户不理解的审计副产物 audit by-products the user does not understand
- 重复标题和说明 duplicate headings and captions
- 不必要的边框、标签、图标 unnecessary borders, labels, icons
- 同一页面中的多个主操作 multiple primary actions on one page
- 不能解释产品价值的动画 animation that explains nothing

**审美很大程度上就是"知道什么时候停"。** Taste is largely knowing when to stop.

## 3. 从画面构图开始，不从组件开始 · Composition first, not components

错误的思考方式 · The wrong frame:

    页面 = Hero + 卡片 + Features + Flow + CTA

正确的思考方式 · The right frame — ask of every screen:

    这一屏首先让用户看到什么？    What does the eye land on first?
    第二眼看哪里？                Where does it go second?
    五秒后理解了什么？            What is understood after five seconds?
    下一步应该做什么？            What should the user do next?

**每一屏只有一个主角。** One protagonist per screen. On the landing page's
first viewport that protagonist is *one* of: the core proposition, a real
CrossAudit workspace, or one legible Generator → Audit → Result path — never
all three shouting at once.

## 4. 排版决定大部分高级感 · Typography carries the quality

先把字体和间距做好，再谈玻璃。 Fix type and spacing before touching glass.

- 正文：中性、清晰的无衬线 neutral sans for body text
- 数字、日志、模型名、代码：等宽 mono for numbers, logs, model ids, code
- 正文行宽 55–75 字符 measure 55–75 characters
- 同一区域最多三级字号 at most three type sizes per region
- 层级靠字号、字重和留白，少靠边框 hierarchy from size, weight and space —
  rarely from borders
- 中文避免过粗、过密、过小 CJK: never too bold, too dense, too small
- 行高宁可稍宽 line-height errs generous, never back-office cramped
- 标题短，不用营销空话 titles short; no marketing filler

页面"不高级"，首先查字体、行宽和间距，而不是缺特效。 When a page reads cheap,
suspect type, measure and spacing first — never a missing effect.

## 5. 视觉参考库 · The reference library

不要笼统地说"像 Apple"。截取具体画面并标注：喜欢它的什么（密度/排版/动效）、
哪些不适合 CrossAudit、移植过来解决什么真实问题。分表建立：导航 · 对话输入 ·
文件输出 · 审计循环 · 异常处理 · 项目列表 · 设置页 · 官网叙事。

Reference concrete screens, annotated — never "like Apple" in the abstract.
The goal is understanding visual decisions, not copying skins.

## 6. 对比审查 · Comparative review (A/B/C)

每个页面保留三个版本 · Keep three versions of every screen:

- **A** 最克制 the most restrained
- **B** 信息最完整 the most complete
- **C** 表现力最强 the most expressive

逐项比较：哪个第一眼最明确？最容易操作？一周后仍耐看？删除后毫无损失的是
什么？哪个效果只是炫技？**最终版本以 A 为基础，吸收 B 的必要信息和 C 的一个
亮点。** The final ships from A, absorbing B's necessary information and
exactly one highlight from C.

## 7. 强制截图迭代 · Mandatory screenshot iteration

代码正确不等于视觉正确。每次设计至少检查 · Code-correct is not
visually-correct. Every design pass checks at minimum:

1440×900 · 1280×800 · 1024×768 · 430×932 · 长文本 long text · 空状态 empty ·
加载 loading · 错误 error · 多文件 multi-file · 中英切换 EN/ZH · 200% zoom ·
Reduce Motion

**每轮只解决一类问题** · One problem class per round, in order:

1. 构图 composition
2. 信息层级 hierarchy
3. 排版 typography
4. 间距 spacing
5. 色彩 color
6. 动效 motion
7. 微交互 micro-interaction

不要一轮重写所有东西——那只是在不同问题之间来回摆动。 Never rewrite everything
in one round; that is oscillation, not iteration.

## 8. 判断权 · The judgement mandate

给设计执行者（人或 AI）的核心指令不是"添加什么"，而是"删除什么"和"根据什么
判断"。 The core instruction, verbatim:

> Before coding, inspect the rendered interface and identify the three most
> damaging visual problems. Fix hierarchy and composition before styling
> details. You may remove redundant sections, cards, borders, labels, and
> copy. Do not preserve the current layout merely because it already exists.
> Produce screenshots at desktop and mobile sizes, critique them against the
> references, and iterate until the page has one clear focal point,
> deliberate typography, controlled density, and no generic SaaS-card
> composition.

## 9. CrossAudit 设计六原则 · The six principles

1. **用户成果高于审计过程。** User outcomes over audit process.
2. **一个界面只有一个主操作。** One primary action per surface.
3. **正常状态安静，风险状态明确。** Normal states are quiet; risk states are
   unmistakable.
4. **玻璃用于控制层，不用于内容层。** Glass belongs to the control plane,
   never the content plane.
5. **动效解释状态变化，不负责装饰。** Motion explains state change; it does
   not decorate.
6. **高级功能渐进展示。** Advanced capability reveals progressively — never
   dumped on a new user at once.

---

真正的方法不是更多形容词，而是：**少量高质量参考 + 明确的取舍规则 + 真实截图
+ 多轮批评与删除。** 页面不是因为做得多而漂亮，而是因为每一个留下来的东西都有
理由。

The method is never more adjectives. It is a few high-quality references,
explicit trade-off rules, real screenshots, and repeated rounds of critique
and deletion. A page is not beautiful because much was made — it is beautiful
because everything that remains has a reason.
