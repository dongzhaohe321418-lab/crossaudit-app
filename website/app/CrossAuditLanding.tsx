"use client";

/* eslint-disable @next/next/no-img-element */
import type { CSSProperties } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

const REPOSITORY = "https://github.com/dongzhaohe321418-lab/crossaudit_v4";
const RELEASES = `${REPOSITORY}/releases/latest`;
const RELEASE_API =
  "https://api.github.com/repos/dongzhaohe321418-lab/crossaudit_v4/releases/latest";

type Language = "en" | "zh";

type ReleaseAsset = {
  name: string;
  browser_download_url: string;
  size: number;
};

type ReleaseInfo = {
  tag_name: string;
  html_url: string;
  assets: ReleaseAsset[];
};

const FALLBACK_RELEASE: ReleaseInfo = {
  tag_name: "v4.14.0",
  html_url: RELEASES,
  assets: [],
};

/* Which audit checkpoint lights each sample-run event (index into flowSteps). */
const EVENT_THRESHOLDS = [2, 4, 5, 6, 6, 7] as const;
const EVENT_TONES = ["generator", "information", "auditor", "generator", "pass", "pass"] as const;

/* Role accent per trunk card: Generator blue at step 3, Auditor violet at step 6. */
const CARD_ROLES = ["", "", "fc-g", "", "", "fc-a"] as const;

const NAV_IDS = ["product", "how", "science", "security"] as const;

const copy = {
  en: {
    nav: ["Product", "How it works", "For science", "Security"],
    github: "GitHub",
    download: "Download for macOS",
    viewSource: "View on GitHub",
    titleA: "Agentic work,",
    titleB: "independently audited.",
    intro:
      "One model does the work. A model from a different provider inspects every committed result before it reaches you.",
    heroMeta: ["macOS", "Apple Silicon", "Open source"],
    heroCaps: "PDF / DOCX / MCP / Skills / HPC / GitHub / EN+中文",
    demo: {
      title: "CrossAudit · Paper review",
      railLabel: "Projects",
      projects: ["Paper review", "Data pipeline", "Grant draft"],
      prompt: "Review this paper rigorously and deliver a PDF.",
      states: ["Understanding", "Working", "Checking", "Revising", "Done"],
      file: "review_notes.md",
      findings: "Auditor: 2 findings",
      passline: "Independent review passed",
      deliver: "review.pdf",
      deliverTag: "Deliverable",
      generator: "Generator",
      auditor: "Auditor",
      vendorA: "provider A",
      vendorB: "provider B",
      contextLabel: "Audit context",
      checks: ["Deterministic checks", "Independent review", "Human admission"],
      roundA: "Round 1 of 3",
      roundB: "Round 2 of 3",
      composer: "Describe the deliverable",
      caption: "One supervised run on loop, with sample data.",
    },
    thesisTitle: "Most agents grade their own homework.",
    thesisBody:
      "Self-review by the same model is not supervision. CrossAudit routes every result through a second provider with no shared reasoning, and delivers only what survives.",
    trackATitle: "A typical agent",
    trackA: ["One model works", "The same model self-checks", "Delivered"],
    trackANote: "No independent evidence.",
    trackBTitle: "CrossAudit",
    trackB: ["You describe the goal", "Generator commits work", "Deterministic checks", "Independent auditor"],
    trackBLoop: "BLOCK returns for bounded revision",
    trackBEnd: "Verified delivery, with receipt",
    trackBNote: "Same-vendor pairs are refused outright.",
    auditTitle: "See the complete path from instruction to admission.",
    auditBody:
      "Scroll through the system. Each handoff changes the active role, trusted boundary, and evidence that CrossAudit preserves.",
    auditTrace: "AUDITED EXECUTION GRAPH",
    auditRound: "8 checkpoints · 3 outcomes",
    evidenceLabel: "Durable evidence",
    flowSteps: [
      ["Prompt and files", "You", "Describe the deliverable, add source files, and choose who should receive an explicit instruction.", "Request and source manifest"],
      ["Bounded run", "CrossAudit", "The controller creates a durable run with provider routes, a round budget, and a recoverable state.", "Run ID and policy snapshot"],
      ["Generator works", "Generator", "The generator writes inside the selected workspace and can use scoped MCP tools, skills, or remote compute.", "Candidate files and tool events"],
      ["Git pins revision", "Git", "CrossAudit commits the candidate before review so the auditor always inspects a stable, addressable result.", "Immutable commit SHA"],
      ["Deterministic gate", "CrossAudit", "Machine checks verify completion, declared outputs, internal paths, and parseable artifact structure first.", "Deterministic check report"],
      ["Independent audit", "Auditor", "A different provider reviews the committed files against the active constitution and returns a structured verdict.", "Verdict and structured findings"],
      ["Controlled loop", "CrossAudit", "PASS advances. BLOCK returns bounded guidance. Provider failure or an exhausted budget requests a human decision.", "Durable run events and revision diff"],
      ["Human admission", "You", "Only a passing revision can produce a one-time receipt. You decide whether that exact result may be admitted.", "Cryptographically bound receipt"],
    ],
    flowEvidence: [
      "TASK.md @ 56a6223",
      "run 7f2e, 3 rounds budgeted",
      "review_notes.md, analysis.md, review.pdf",
      "commit 9f31c02, +412 lines",
      "4 checks ran, all passed",
      "2 findings: methodology, citations",
    ],
    flowExits: [
      ["PASS", "Receipt bound. You admit or reject."],
      ["BLOCKED", "Guidance returns, round 2 of 3"],
      ["NEEDS YOU", "One specific question"],
    ],
    flowBoundary: "The auditor sees committed work, not the generator's private chain of thought.",
    eventsLabel: "Sample run",
    events: [
      ["14:08", "Generator created review.pdf"],
      ["14:09", "Deterministic checks passed"],
      ["14:10", "Auditor found 2 issues"],
      ["14:11", "Revision started automatically"],
      ["14:13", "Independent review passed"],
      ["14:13", "Deliverable ready"],
    ],
    generator: "Generator",
    auditor: "Auditor",
    controller: "CrossAudit",
    promptTitle: "One prompt. The whole loop.",
    promptBody:
      "You state the goal once. Focus, format, file handling, and revision rounds are decided inside the loop, and recorded.",
    promptQuote:
      "Review this paper rigorously, focus on methodology and statistical claims, and deliver a PDF.",
    promptSteps: [
      ["Reads the intent", "Methodology and statistical claims become the review focus."],
      ["Picks the format", "A PDF deliverable is declared before work starts."],
      ["Uses the attachments", "The paper is read from the files you dropped in."],
      ["Generates and commits", "Draft work lands in your workspace as pinned revisions."],
      ["Audits and revises", "An independent provider blocks, the generator repairs, rounds stay bounded."],
      ["Delivers one file", "You receive the PDF you asked for, with its evidence one click deeper."],
    ],
    promptCore: "CrossAudit asks only when the decision is consequential.",
    workspaceTitle: "The real workspace.",
    workspaceBody:
      "Projects, chats, files, model control, and audit context in one native macOS window. These are current-release screenshots, not renders.",
    shotSteps: [
      ["One conversation at the center", "Projects and pinned chats sit on the left rail. The run you are reading is the whole center column."],
      ["The composer carries the controls", "Files, roles, model choice, and reasoning effort travel with the message instead of a settings maze."],
      ["Audit context on demand", "Findings, rounds, and evidence expand beside the same conversation when you ask for them."],
    ],
    workspaceAlt: "The CrossAudit workspace: project rail, conversation, and composer.",
    auditShotAlt: "The same conversation with independent audit context expanded.",
    openFullSize: "Open full-resolution image",
    indepTitleA: "Generated by one model.",
    indepTitleB: "Checked by another.",
    indepBody: "That single sentence is the product. The details below are how it stays true.",
    indepToggle: "How the audit stays independent",
    indepItems: [
      ["Different providers, enforced", "Generator and auditor must come from different vendors. Same-vendor pairs are refused."],
      ["No shared reasoning", "The auditor never sees the generator's private chain of thought, only committed work."],
      ["Immutable review target", "Every audit runs against a pinned Git commit, never a moving directory."],
      ["Checks before judgement", "Deterministic verification of outputs and structure runs before any model opinion."],
      ["Bounded, fail-closed loops", "Revision rounds have a budget. Failure pauses and asks; it never approves."],
      ["One-time receipt", "Admission binds verdict, constitution version, and commit. Change a byte and it no longer verifies."],
    ],
    capTitle: "Everything the agent needs. Nothing undisclosed.",
    capBody:
      "Capabilities arrive scoped to a project and visible in the run record. Depth appears when the work calls for it.",
    capGroups: [
      ["Workspace", [
        ["Local projects", "Folders you choose, Git history included"],
        ["PDF and DOCX delivery", "Complete documents rendered locally"],
        ["Background runs", "Tasks continue while you work elsewhere"],
        ["Bilingual interface", "English and Chinese, one workspace"],
      ]],
      ["Integrations", [
        ["Paired GitHub repos", "Working and audit history as plain Git"],
        ["MCP servers", "Local stdio or streamable HTTP, allowlisted"],
        ["Reusable skills", "Approved procedures the generator can call"],
        ["HPC and Slurm", "Bounded jobs on your own clusters"],
      ]],
      ["Control", [
        ["Model switching", "Provider, model, and effort per role"],
        ["Token usage", "Local-first, with labeled estimates"],
        ["Project isolation", "Runs cannot reach outside their scope"],
      ]],
      ["Resilience", [
        ["Crash recovery", "Durable runs survive a dead worker"],
        ["Provider fallback", "Routed within cost caps you set"],
        ["Fail-closed budgets", "Hard limits stop work, never approve it"],
      ]],
    ],
    sciTitle: "For research that outgrows a laptop.",
    sciBody:
      "The generator can drive your own clusters as a policy-bounded calculator. The conclusions still face the same independent audit.",
    sciPipeline: ["Generator", "Resource policy", "SSH / Slurm", "Remote run", "Declared results", "Analysis", "Independent audit"],
    sciFacts: [
      ["Remote-owned execution", "The cluster owns the job. Closing your Mac does not stop it."],
      ["Live scheduler truth", "Queue state, logs, and outputs stream back as they happen."],
      ["Audited conclusions", "Hard resource ceilings you set, and results that still face review."],
    ],
    secTitle: "Security by architecture, not adjectives.",
    secBody: "Each guarantee below is a mechanism you can read in the source, not a promise.",
    secRows: [
      ["API keys", "macOS Keychain, write-only"],
      ["Project data", "Local folders you choose"],
      ["Console", "Loopback only, token-gated"],
      ["Generator and auditor", "Separate providers, enforced"],
      ["History", "Paired Git repositories"],
      ["External capabilities", "Explicit, scoped, revocable"],
      ["Destructive actions", "Typed human confirmation"],
    ],
    dlTitle: "Download from the source.",
    dlBody: "The installer and checksum come directly from the official GitHub release. Nothing is repackaged.",
    dlAltLabel: "Prefer to build it yourself?",
    dlClone: "git clone https://github.com/dongzhaohe321418-lab/crossaudit_v4",
    dlCloneNote: "Then follow the README. The website you are reading lives in the same repository.",
    latest: "Latest release",
    loading: "Checking the latest GitHub release",
    live: "Latest stable release confirmed by GitHub",
    fallback: "GitHub API is unavailable. The official latest-release link remains available.",
    noDmg: "This release lists no DMG asset. Open the release page or build from source.",
    checksum: "SHA-256 checksum",
    notes: "Release notes",
    size: "Installer size",
    integrity:
      "This community build is ad-hoc signed and not Apple-notarized. macOS may ask you to confirm its first launch.",
    footerLinks: ["GitHub", "Documentation", "Releases", "Security", "License"],
    footerNote: "Open source software for inspectable AI work.",
  },
  zh: {
    nav: ["产品", "工作方式", "科研", "安全"],
    github: "GitHub",
    download: "下载 macOS 版",
    viewSource: "查看 GitHub",
    titleA: "Agent 自主工作，",
    titleB: "独立系统审计。",
    intro: "一个模型完成工作，另一家厂商的模型在交付前检查每个已提交的结果。",
    heroMeta: ["macOS", "Apple Silicon", "开源"],
    heroCaps: "PDF / DOCX / MCP / Skills / HPC / GitHub / 中英双语",
    demo: {
      title: "CrossAudit · 论文评审",
      railLabel: "项目",
      projects: ["论文评审", "数据管线", "基金初稿"],
      prompt: "严格评审这篇论文，并交付一份 PDF。",
      states: ["正在理解", "正在工作", "正在检查", "正在修订", "已完成"],
      file: "review_notes.md",
      findings: "审计者：2 个发现",
      passline: "独立审查通过",
      deliver: "review.pdf",
      deliverTag: "交付物",
      generator: "生成者",
      auditor: "审计者",
      vendorA: "厂商 A",
      vendorB: "厂商 B",
      contextLabel: "审计上下文",
      checks: ["确定性检查", "独立审查", "人工准入"],
      roundA: "第 1/3 轮",
      roundB: "第 2/3 轮",
      composer: "描述你要的交付物",
      caption: "循环播放的一次受监督运行，示例数据。",
    },
    thesisTitle: "多数 Agent 在给自己的作业打分。",
    thesisBody:
      "同一个模型的自查不是监督。CrossAudit 让每个结果经过另一家厂商的模型审查，双方不共享推理，只有通过的结果才会交付。",
    trackATitle: "普通 Agent",
    trackA: ["一个模型工作", "同一模型自查", "直接交付"],
    trackANote: "没有独立证据。",
    trackBTitle: "CrossAudit",
    trackB: ["你描述目标", "生成者提交工作", "确定性检查", "独立审计者"],
    trackBLoop: "BLOCK 返回，有界修订",
    trackBEnd: "验证后交付，附凭证",
    trackBNote: "同厂配对会被直接拒绝。",
    auditTitle: "查看从指令到准入的完整路径。",
    auditBody: "滚动查看系统流程。每次交接都会同步改变当前角色、可信边界和 CrossAudit 保存的证据。",
    auditTrace: "受审计执行图",
    auditRound: "8 个检查点 · 3 种结果",
    evidenceLabel: "持久证据",
    flowSteps: [
      ["指令与文件", "你", "描述交付物、加入源文件，并在需要时明确指定生成者或审计者接收指令。", "请求与源文件清单"],
      ["有边界的运行", "CrossAudit", "控制器创建持久运行，锁定模型路由、审计轮数上限和可恢复状态。", "运行 ID 与策略快照"],
      ["生成者执行", "生成者", "生成者在所选工作区写入文件，并可使用限定范围的 MCP、Skills 或远程计算。", "候选文件与工具事件"],
      ["Git 固定修订", "Git", "CrossAudit 在审查前提交候选结果，确保审计者检查的是稳定、可定位的版本。", "不可变 Commit SHA"],
      ["确定性门禁", "CrossAudit", "先检查完成性、声明输出、内部路径和交付物结构是否可解析。", "确定性检查报告"],
      ["独立审计", "审计者", "另一厂商根据当前宪法审查已提交文件，并返回结构化结论。", "结论与结构化发现"],
      ["受控循环", "CrossAudit", "PASS 继续准入，BLOCK 返回限定修订指导，厂商故障或预算耗尽则请求人工决定。", "持久运行事件与修订差异"],
      ["人工准入", "你", "只有通过的修订才能产生一次性凭证，由你决定是否准入这个精确结果。", "加密绑定的准入凭证"],
    ],
    flowEvidence: [
      "TASK.md @ 56a6223",
      "run 7f2e，预算 3 轮",
      "review_notes.md, analysis.md, review.pdf",
      "commit 9f31c02，+412 行",
      "4 项检查全部通过",
      "2 个发现：方法学、引用",
    ],
    flowExits: [
      ["PASS", "凭证已绑定，由你准入或拒绝。"],
      ["BLOCKED", "指导返回，进入第 2/3 轮"],
      ["需要你", "一个具体问题"],
    ],
    flowBoundary: "审计者看到已提交结果，而不是生成者的私有思维链。",
    eventsLabel: "示例运行",
    events: [
      ["14:08", "生成者创建 review.pdf"],
      ["14:09", "确定性检查通过"],
      ["14:10", "审计者发现 2 个问题"],
      ["14:11", "自动开始修订"],
      ["14:13", "独立审查通过"],
      ["14:13", "交付物就绪"],
    ],
    generator: "生成者",
    auditor: "审计者",
    controller: "CrossAudit",
    promptTitle: "一条指令，完整循环。",
    promptBody: "目标只需说一次。重点、格式、文件处理与修订轮次都在循环内决定，并全部留下记录。",
    promptQuote: "严格评审这篇论文，重点关注方法学与统计论断，并交付一份 PDF。",
    promptSteps: [
      ["读懂意图", "方法学与统计论断自动成为评审重点。"],
      ["选定格式", "PDF 交付物在开工前就被声明。"],
      ["使用附件", "论文直接从你拖入的文件中读取。"],
      ["生成并提交", "草稿以固定修订的形式进入你的工作区。"],
      ["审计与修订", "独立厂商阻塞，生成者修复，轮次始终有界。"],
      ["交付一个文件", "你得到所要的那份 PDF，证据在下一层随时可查。"],
    ],
    promptCore: "只有后果重大的决定，CrossAudit 才会问你。",
    workspaceTitle: "真实的工作区。",
    workspaceBody: "项目、对话、文件、模型控制与审计上下文都在一个原生 macOS 窗口。以下是当前发行版的真实截图，不是渲染图。",
    shotSteps: [
      ["对话在正中央", "项目与置顶对话在左栏，你正在读的这次运行就是整个中央列。"],
      ["控制随输入框走", "文件、角色、模型与推理强度跟着消息走，而不是藏进设置迷宫。"],
      ["审计上下文按需展开", "发现、轮次与证据在同一对话旁展开，只在你需要时出现。"],
    ],
    workspaceAlt: "CrossAudit 工作区：项目栏、对话与输入框。",
    auditShotAlt: "同一对话旁展开的独立审计上下文。",
    openFullSize: "打开全分辨率图片",
    indepTitleA: "一个模型生成，",
    indepTitleB: "另一个模型检查。",
    indepBody: "这句话就是产品本身。下面的细节让它始终为真。",
    indepToggle: "审计如何保持独立",
    indepItems: [
      ["强制不同厂商", "生成者与审计者必须来自不同厂商，同厂配对会被拒绝。"],
      ["不共享推理", "审计者永远看不到生成者的私有思维链，只看已提交的工作。"],
      ["不可变的审查对象", "每次审计都针对固定的 Git 提交，而不是移动中的目录。"],
      ["先检查后判断", "输出与结构的确定性验证先于任何模型意见。"],
      ["有界且失败即关闭", "修订轮次有预算。失败会暂停并询问，绝不会变成批准。"],
      ["一次性凭证", "准入把结论、宪法版本与提交绑定在一起。改动一个字节即无法通过校验。"],
    ],
    capTitle: "Agent 需要的一切，全部公开声明。",
    capBody: "能力以项目为范围接入，并出现在运行记录里。深度只在工作需要时展开。",
    capGroups: [
      ["工作区", [
        ["本地项目", "你选择的文件夹，含 Git 历史"],
        ["PDF 与 DOCX 交付", "完整文档在本地渲染"],
        ["后台运行", "任务在你忙别的事时继续"],
        ["双语界面", "中英文同一个工作区"],
      ]],
      ["集成", [
        ["成对 GitHub 仓库", "工作与审计历史都是普通 Git"],
        ["MCP 服务", "本地 stdio 或 HTTP，白名单制"],
        ["可复用 Skills", "生成者可调用的既定流程"],
        ["HPC 与 Slurm", "在你自己的集群上运行有界任务"],
      ]],
      ["控制", [
        ["模型切换", "按角色选择厂商、模型与强度"],
        ["Token 用量", "本地优先，估算值明确标注"],
        ["项目隔离", "运行无法越出自身范围"],
      ]],
      ["韧性", [
        ["崩溃恢复", "持久运行不怕工作进程挂掉"],
        ["厂商回退", "在你设定的成本上限内路由"],
        ["失败即关闭", "硬限额只会停下，不会批准"],
      ]],
    ],
    sciTitle: "为超出笔记本的研究准备。",
    sciBody: "生成者可以把你的集群当作受策略约束的计算器来驱动，而结论仍要面对同样的独立审计。",
    sciPipeline: ["生成者", "资源策略", "SSH / Slurm", "远程运行", "声明结果", "分析", "独立审计"],
    sciFacts: [
      ["远程持有执行", "任务归集群所有，合上 Mac 也不会停止。"],
      ["调度器实况", "队列状态、日志与输出实时流回。"],
      ["结论仍受审计", "资源上限由你设定，结果仍需通过审查。"],
    ],
    secTitle: "安全来自架构，不是形容词。",
    secBody: "下面每一条保证都是可以在源码里读到的机制，而不是承诺。",
    secRows: [
      ["API 密钥", "macOS 钥匙串，只写不读"],
      ["项目数据", "你选择的本地文件夹"],
      ["控制台", "仅本机回环，令牌门禁"],
      ["生成者与审计者", "强制分属不同厂商"],
      ["历史记录", "成对的 Git 仓库"],
      ["外部能力", "显式、限定范围、可撤销"],
      ["破坏性操作", "需人工键入确认"],
    ],
    dlTitle: "直接从源头下载。",
    dlBody: "安装包与校验文件直接来自官方 GitHub Release，未经任何重新打包。",
    dlAltLabel: "想自己构建？",
    dlClone: "git clone https://github.com/dongzhaohe321418-lab/crossaudit_v4",
    dlCloneNote: "然后按 README 操作。你正在看的这个网站也在同一个仓库里。",
    latest: "最新版本",
    loading: "正在检查 GitHub 最新版本",
    live: "已通过 GitHub 确认最新稳定版本",
    fallback: "GitHub API 暂时不可用，官方最新版本链接仍可访问。",
    noDmg: "该版本未列出 DMG 资产。请打开 Release 页面或从源码构建。",
    checksum: "SHA-256 校验",
    notes: "版本说明",
    size: "安装包大小",
    integrity: "此社区构建采用临时签名，尚未通过 Apple 公证。macOS 可能要求你确认首次启动。",
    footerLinks: ["GitHub", "文档", "Releases", "安全", "许可证"],
    footerNote: "为可检查的 AI 工作而构建的开源软件。",
  },
} as const;

function formatBytes(bytes: number) {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function delay(index: number): CSSProperties {
  return { "--i": index } as CSSProperties;
}

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

/* The hero product sketch: a faithful, obviously drawn miniature of the real
   workspace (left project rail, one conversation, audit context) that plays
   one supervised run on an 11 second loop. Pure CSS keyframes; paused while
   offscreen; static end-state under reduced motion. */
function DemoWindow({ demo }: { demo: (typeof copy)["en"]["demo"] | (typeof copy)["zh"]["demo"] }) {
  return (
    <figure className="demo-shell">
      <div className="demo-window" data-pause-offscreen aria-hidden="true">
        <div className="demo-title">
          <BrandMark />
          <span>{demo.title}</span>
        </div>
        <div className="demo-body">
          <div className="demo-rail">
            <small>{demo.railLabel}</small>
            {demo.projects.map((project, index) => (
              <span key={project} className={index === 0 ? "active" : ""}>
                {project}
              </span>
            ))}
          </div>
          <div className="demo-main">
            <p className="dw-msg">{demo.prompt}</p>
            <div className="dw-states">
              {demo.states.map((state, index) => (
                <span key={state} className={`dw-state dw-state-${index + 1}`}>
                  <i />
                  {state}
                </span>
              ))}
            </div>
            <p className="dw-file">
              <i />
              {demo.file}
            </p>
            <p className="dw-findings">{demo.findings}</p>
            <p className="dw-file dw-file2">
              <i />
              {demo.deliver}
            </p>
            <p className="dw-pass">{demo.passline}</p>
            <p className="dw-deliver">
              <span>{demo.deliverTag}</span>
              {demo.deliver}
            </p>
            <p className="demo-composer">{demo.composer}</p>
          </div>
          <div className="demo-aside">
            <small className="demo-aside-label">{demo.contextLabel}</small>
            <span className="demo-role demo-role-g">
              {demo.generator}
              <small>{demo.vendorA}</small>
            </span>
            <span className="demo-role demo-role-a">
              {demo.auditor}
              <small>{demo.vendorB}</small>
            </span>
            <p className="demo-rounds">
              <span className="dw-round-1">{demo.roundA}</span>
              <span className="dw-round-2">{demo.roundB}</span>
            </p>
            <ul>
              {demo.checks.map((check, index) => (
                <li key={check} className={index < 2 ? `dwc dwc-${index + 1}` : ""}>
                  {check}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <figcaption>{demo.caption}</figcaption>
    </figure>
  );
}

export function CrossAuditLanding() {
  const [language, setLanguage] = useState<Language>("en");
  const [release, setRelease] = useState<ReleaseInfo>(FALLBACK_RELEASE);
  const [releaseState, setReleaseState] = useState<"loading" | "live" | "fallback">("loading");
  const [auditState, setAuditState] = useState(0);
  const [shotState, setShotState] = useState(0);
  const [indepOpen, setIndepOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [navActive, setNavActive] = useState<string>("product");
  const flowRef = useRef<HTMLDivElement>(null);
  const shotRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const t = copy[language];

  useEffect(() => {
    const savedLanguage = window.localStorage.getItem("crossaudit-site-language");
    window.queueMicrotask(() => {
      if (savedLanguage === "zh" || savedLanguage === "en") setLanguage(savedLanguage);
    });
  }, []);

  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    window.localStorage.setItem("crossaudit-site-language", language);
  }, [language]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(RELEASE_API, {
      headers: { Accept: "application/vnd.github+json" },
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`GitHub returned ${response.status}`);
        return response.json() as Promise<ReleaseInfo>;
      })
      .then((latest) => {
        setRelease(latest);
        setReleaseState("live");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setReleaseState("fallback");
      });
    return () => controller.abort();
  }, []);

  /* Scroll drives the audited execution graph. */
  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const element = flowRef.current;
    if (!element || reduceMotion.matches) return;
    const chapters = Array.from(element.querySelectorAll<HTMLElement>("[data-flow-step]"));
    const observer = new IntersectionObserver(
      (entries) => {
        const active = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!active) return;
        const next = Number((active.target as HTMLElement).dataset.flowStep);
        if (Number.isInteger(next)) setAuditState(next);
      },
      { rootMargin: "-36% 0px -48%", threshold: [0, 0.25, 0.55, 0.8] },
    );
    chapters.forEach((chapter) => observer.observe(chapter));
    return () => observer.disconnect();
  }, []);

  /* Scroll drives the workspace screenshot focus. */
  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const element = shotRef.current;
    if (!element || reduceMotion.matches) return;
    const steps = Array.from(element.querySelectorAll<HTMLElement>("[data-shot-step]"));
    const observer = new IntersectionObserver(
      (entries) => {
        const active = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!active) return;
        const next = Number((active.target as HTMLElement).dataset.shotStep);
        if (Number.isInteger(next)) setShotState(next);
      },
      { rootMargin: "-40% 0px -40%", threshold: [0, 0.3, 0.6] },
    );
    steps.forEach((step) => observer.observe(step));
    return () => observer.disconnect();
  }, []);

  /* Gentle reveal on entry runs from the inline script in layout.tsx, not a
     React effect, so a slow or failed hydration never leaves a section blank. */

  /* Header compression + section spy + offscreen animation pause, all via
     observers; no scroll listeners. */
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const observers: IntersectionObserver[] = [];
    if (sentinel) {
      const headerObserver = new IntersectionObserver(
        ([entry]) => setScrolled(!entry.isIntersecting),
        { rootMargin: "0px" },
      );
      headerObserver.observe(sentinel);
      observers.push(headerObserver);
    }
    const spy = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setNavActive(visible.target.id);
      },
      { rootMargin: "-30% 0px -55%", threshold: [0, 0.2] },
    );
    NAV_IDS.forEach((id) => {
      const section = document.getElementById(id);
      if (section) spy.observe(section);
    });
    observers.push(spy);
    const liveObserver = new IntersectionObserver(
      (entries) =>
        entries.forEach((entry) => entry.target.classList.toggle("is-live", entry.isIntersecting)),
      { rootMargin: "12% 0px" },
    );
    document
      .querySelectorAll<HTMLElement>("[data-pause-offscreen]")
      .forEach((element) => liveObserver.observe(element));
    observers.push(liveObserver);
    return () => observers.forEach((observer) => observer.disconnect());
  }, []);

  const assets = useMemo(() => {
    const dmg = release.assets.find((asset) => asset.name.endsWith(".dmg"));
    const checksum = release.assets.find((asset) => asset.name.endsWith(".sha256"));
    return { dmg, checksum };
  }, [release]);

  const releaseVersion = release.tag_name.replace(/^v/, "");

  return (
    <main>
      <a className="skip-link" href="#main-content">
        {language === "zh" ? "跳到主要内容" : "Skip to main content"}
      </a>
      <div className="top-sentinel" ref={sentinelRef} aria-hidden="true" />

      <header className="site-header" data-scrolled={scrolled ? "true" : undefined}>
        <a className="brand" href="#product" aria-label="CrossAudit home">
          <BrandMark />
          <span>CrossAudit</span>
          <em>v{releaseVersion}</em>
        </a>
        <nav className="desktop-nav" aria-label="Site">
          {t.nav.map((item, index) => (
            <a
              key={item}
              href={`#${NAV_IDS[index]}`}
              aria-current={navActive === NAV_IDS[index] ? "true" : undefined}
            >
              {item}
            </a>
          ))}
          <a href={REPOSITORY}>{t.github}</a>
        </nav>
        <div className="header-actions">
          <button
            className="text-control"
            type="button"
            onClick={() => setLanguage(language === "en" ? "zh" : "en")}
            aria-label={language === "en" ? "切换到中文" : "Switch to English"}
          >
            {language === "en" ? "中" : "EN"}
          </button>
          <a className="header-download" href="#download">
            {t.download}
          </a>
        </div>
      </header>

      <div id="main-content">
        {/* 1 · Hero */}
        <section className="hero section-shell" id="product">
          <div className="hero-copy">
            <h1>
              <span>{t.titleA}</span> <span className="accent-line">{t.titleB}</span>
            </h1>
            <p className="hero-intro">{t.intro}</p>
            <div className="hero-actions">
              <a className="button button-primary" href={assets.dmg?.browser_download_url ?? RELEASES}>
                {t.download}
              </a>
              <a className="button button-secondary" href={REPOSITORY}>
                {t.viewSource}
              </a>
            </div>
            <p className="hero-meta">
              <span>v{releaseVersion}</span>
              {t.heroMeta.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </p>
            <p className="hero-caps">{t.heroCaps}</p>
          </div>
          <DemoWindow demo={t.demo} />
        </section>

        {/* 2 · Thesis */}
        <section className="thesis-section section-shell" id="thesis">
          <div className="section-heading" data-reveal>
            <h2>{t.thesisTitle}</h2>
            <p>{t.thesisBody}</p>
          </div>
          <div className="thesis-tracks" data-reveal>
            <article className="track track-plain">
              <h3>{t.trackATitle}</h3>
              <ol className="track-steps">
                {t.trackA.map((step) => (
                  <li className="step" key={step}>
                    <span className="step-dot" aria-hidden="true" />
                    <span className="step-label">{step}</span>
                  </li>
                ))}
              </ol>
              <p className="track-outcome fail">{t.trackANote}</p>
            </article>
            <article className="track track-crossaudit">
              <h3>{t.trackBTitle}</h3>
              <ol className="track-steps has-loop">
                {t.trackB.map((step, index) => (
                  <li
                    className={`step ${index === 1 ? "is-g" : ""} ${index === 3 ? "is-a" : ""}`}
                    key={step}
                  >
                    <span className="step-dot" aria-hidden="true" />
                    <span className="step-label">{step}</span>
                  </li>
                ))}
                <span className="loop-edge" aria-hidden="true" />
                <li className="loop-note">
                  <span aria-hidden="true">↑ </span>
                  {t.trackBLoop}
                </li>
                <li className="step step-pass">
                  <span className="step-dot" aria-hidden="true" />
                  <span className="step-label">{t.trackBEnd}</span>
                </li>
              </ol>
              <p className="track-outcome pass">{t.trackBNote}</p>
            </article>
          </div>
        </section>

        {/* 3 · Audited execution graph */}
        <section className="audit-section section-shell" id="how">
          <div className="section-heading" data-reveal>
            <h2>{t.auditTitle}</h2>
            <p>{t.auditBody}</p>
          </div>
          <div className="flow-scroll-layout" ref={flowRef}>
            <div
              className="flow-map-sticky"
              data-pause-offscreen
              role="region"
              aria-label={t.auditTrace}
            >
              <div className="flow-map-head">
                <div>
                  <span>{t.auditTrace}</span>
                </div>
                <span>{t.eventsLabel}</span>
              </div>
              <div className="flow-canvas">
                <i className="fc-trunk" aria-hidden="true" />
                {t.flowSteps.slice(0, 6).map(([title, role], index) => (
                  <button
                    type="button"
                    className={`fc-card ${CARD_ROLES[index]} ${auditState === index ? "active" : ""} ${auditState > index ? "reached" : ""}`}
                    style={{ gridRow: index + 1 }}
                    aria-pressed={auditState === index}
                    onClick={() => setAuditState(index)}
                    key={title}
                  >
                    <span className="fc-head">
                      <strong>{title}</strong>
                      <small>{role}</small>
                    </span>
                    <code>{t.flowEvidence[index]}</code>
                  </button>
                ))}
                <div className={`fc-bracket ${auditState === 6 ? "active" : ""}`} aria-hidden="true">
                  <svg viewBox="0 0 36 100" preserveAspectRatio="none" focusable="false">
                    <defs>
                      <linearGradient id="fcb-grad" x1="0" y1="1" x2="0" y2="0">
                        <stop offset="0" stopColor="#9a7cff" />
                        <stop offset="1" stopColor="#5ea0ff" />
                      </linearGradient>
                    </defs>
                    <path
                      className="fcb-main"
                      d="M 36 69 H 6 V 8 H 30"
                      fill="none"
                      vectorEffect="non-scaling-stroke"
                    />
                    <path
                      className="fcb-flow"
                      d="M 36 69 H 6 V 8 H 30"
                      fill="none"
                      vectorEffect="non-scaling-stroke"
                    />
                  </svg>
                  <i />
                </div>
                <div className="fc-exits">
                  {t.flowExits.map(([title, body], index) => (
                    <button
                      type="button"
                      className={`fc-exit fc-exit-${index} ${
                        (auditState === 7 && index === 0) || (auditState === 6 && index === 1)
                          ? "active"
                          : ""
                      }`}
                      onClick={() => setAuditState(index === 0 ? 7 : 6)}
                      key={title}
                    >
                      <strong>{title}</strong>
                      <span>{body}</span>
                    </button>
                  ))}
                </div>
              </div>
              <p className="flow-now" aria-live="polite">
                <span key={auditState}>0{auditState + 1}</span>
                <em>{t.evidenceLabel}</em>
                <strong key={`evidence-${auditState}`}>{t.flowSteps[auditState][3]}</strong>
              </p>
              <div className="flow-events" aria-label={t.eventsLabel}>
                <span className="flow-events-label">{t.eventsLabel}</span>
                {t.events.map(([time, text], index) => (
                  <p
                    key={text}
                    className={`event-${EVENT_TONES[index]} ${auditState >= EVENT_THRESHOLDS[index] ? "active" : ""}`}
                  >
                    <span>{time}</span>
                    <i aria-hidden="true" />
                    {text}
                  </p>
                ))}
              </div>
              <p className="flow-boundary">{t.flowBoundary}</p>
            </div>
            <div className="flow-chapters">
              {t.flowSteps.map(([title, role, body, evidence], index) => (
                <article
                  className={auditState === index ? "active" : ""}
                  data-flow-step={index}
                  aria-current={auditState === index ? "step" : undefined}
                  key={title}
                >
                  <button type="button" onClick={() => setAuditState(index)}>
                    <span>0{index + 1}</span>
                    <small>{role}</small>
                    <h3>{title}</h3>
                    <p>{body}</p>
                    <strong>{evidence}</strong>
                  </button>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* 4 · One prompt, full loop */}
        <section className="prompt-section section-shell" id="loop">
          <div className="section-heading" data-reveal>
            <h2>{t.promptTitle}</h2>
            <p>{t.promptBody}</p>
          </div>
          <div className="prompt-grid">
            <blockquote className="prompt-quote" data-reveal>
              <p>{t.promptQuote}</p>
              <footer>{t.promptCore}</footer>
            </blockquote>
            <ol className="prompt-steps">
              {t.promptSteps.map(([title, body], index) => (
                <li key={title} data-reveal style={delay(index)}>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* 5 · Workspace */}
        <section className="workspace-section section-shell" id="workspace">
          <div className="section-heading" data-reveal>
            <h2>{t.workspaceTitle}</h2>
            <p>{t.workspaceBody}</p>
          </div>
          <div className="shot-layout" ref={shotRef}>
            <div className={`shot-sticky shot-${shotState}`} data-reveal>
              <figure className="shot-frame">
                <a
                  className="capture-link"
                  href="/crossaudit-workspace.png"
                  target="_blank"
                  rel="noreferrer"
                  aria-label={t.openFullSize}
                >
                  <img
                    className="shot-base"
                    src="/crossaudit-workspace-1600.png"
                    srcSet="/crossaudit-workspace-960.png 960w, /crossaudit-workspace-1600.png 1600w, /crossaudit-workspace.png 2704w"
                    sizes="(max-width: 72rem) calc(100vw - 3rem), 56rem"
                    width={2704}
                    height={1824}
                    fetchPriority="low"
                    decoding="async"
                    alt={t.workspaceAlt}
                  />
                  <img
                    className="shot-audit"
                    src="/crossaudit-audit-1600.png"
                    srcSet="/crossaudit-audit-960.png 960w, /crossaudit-audit-1600.png 1600w, /crossaudit-audit.png 2704w"
                    sizes="(max-width: 72rem) calc(100vw - 3rem), 56rem"
                    width={2704}
                    height={1824}
                    loading="lazy"
                    decoding="async"
                    alt={t.auditShotAlt}
                  />
                </a>
                <figcaption>
                  {shotState === 2 ? t.auditShotAlt : t.workspaceAlt}{" "}
                  <a
                    href={shotState === 2 ? "/crossaudit-audit.png" : "/crossaudit-workspace.png"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t.openFullSize}
                  </a>
                </figcaption>
              </figure>
            </div>
            <div className="shot-steps">
              {t.shotSteps.map(([title, body], index) => (
                <article
                  key={title}
                  data-shot-step={index}
                  className={shotState === index ? "active" : ""}
                >
                  <button type="button" onClick={() => setShotState(index)}>
                    <h3>{title}</h3>
                    <p>{body}</p>
                  </button>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* 6 · Independent audit */}
        <section className="indep-section section-shell" id="audit">
          <div className="indep-statement" data-reveal>
            <h2>
              <span className="statement-g">{t.indepTitleA}</span>{" "}
              <span className="statement-a">{t.indepTitleB}</span>
            </h2>
            <p>{t.indepBody}</p>
            <button
              type="button"
              className="indep-toggle"
              aria-expanded={indepOpen}
              aria-controls="indep-view"
              onClick={() => setIndepOpen((open) => !open)}
            >
              <span>{t.indepToggle}</span>
              <i aria-hidden="true" />
            </button>
          </div>
          <div id="indep-view" className="indep-view" hidden={!indepOpen}>
            <ul>
              {t.indepItems.map(([title, body]) => (
                <li key={title}>
                  <strong>{title}</strong>
                  <span>{body}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* 7 · Capabilities */}
        <section className="cap-section section-shell" id="capabilities">
          <div className="section-heading" data-reveal>
            <h2>{t.capTitle}</h2>
            <p>{t.capBody}</p>
          </div>
          <div className="capability-grid">
            {t.capGroups.map(([group, items], groupIndex) => (
              <div className="cap-group" key={group as string} data-reveal style={delay(groupIndex)}>
                <h3>{group as string}</h3>
                <ul>
                  {(items as ReadonlyArray<readonly [string, string]>).map(([label, body]) => (
                    <li key={label}>
                      <strong>{label}</strong>
                      <span>{body}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        {/* 8 · Science / HPC */}
        <section className="science-section section-shell" id="science">
          <div className="section-heading" data-reveal>
            <h2>{t.sciTitle}</h2>
            <p>{t.sciBody}</p>
          </div>
          <div className="sci-pipeline" data-reveal aria-label={language === "zh" ? "远程计算流程" : "Remote compute pipeline"}>
            {t.sciPipeline.map((stage, index) => (
              <span key={stage} className={index === 0 ? "chip-g" : index === t.sciPipeline.length - 1 ? "chip-a" : ""}>
                {stage}
              </span>
            ))}
          </div>
          <div className="sci-facts">
            {t.sciFacts.map(([title, body], index) => (
              <article key={title} data-reveal style={delay(index)}>
                <h3>{title}</h3>
                <p>{body}</p>
              </article>
            ))}
          </div>
        </section>

        {/* 9 · Security */}
        <section className="security-section section-shell" id="security">
          <div className="section-heading" data-reveal>
            <h2>{t.secTitle}</h2>
            <p>{t.secBody}</p>
          </div>
          <dl className="security-ledger" data-reveal>
            {t.secRows.map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* 10 · Download */}
        <section className="download-section section-shell" id="download" data-reveal>
          <div className="download-intro">
            <h2>{t.dlTitle}</h2>
            <p>{t.dlBody}</p>
            <p className="clone-label">{t.dlAltLabel}</p>
            <code className="clone-line">{t.dlClone}</code>
            <p className="clone-note">{t.dlCloneNote}</p>
          </div>
          <div className="download-panel">
            <p className="release-line">
              <span>{t.latest}</span>
              <strong>{releaseVersion}</strong>
            </p>
            <p className={`release-state ${releaseState}`} role="status">
              {releaseState === "loading" ? t.loading : releaseState === "live" ? t.live : t.fallback}
            </p>
            {releaseState === "live" && !assets.dmg ? (
              <p className="release-nodmg">{t.noDmg}</p>
            ) : null}
            <div className="download-actions">
              <a
                className="button button-primary"
                href={assets.dmg?.browser_download_url ?? RELEASES}
              >
                {t.download}
              </a>
              <a className="button button-secondary" href={REPOSITORY}>
                {t.viewSource}
              </a>
            </div>
            <ul className="release-meta">
              {assets.dmg ? (
                <li>
                  {t.size}: <strong>{formatBytes(assets.dmg.size)}</strong>
                </li>
              ) : null}
              {assets.checksum ? (
                <li>
                  <a href={assets.checksum.browser_download_url}>{t.checksum}</a>
                </li>
              ) : null}
              <li>
                <a href={release.html_url}>{t.notes}</a>
              </li>
            </ul>
            <p className="integrity-note">{t.integrity}</p>
          </div>
        </section>
      </div>

      <footer>
        <div className="footer-brand">
          <BrandMark />
          <span>CrossAudit</span>
        </div>
        <p>{t.footerNote}</p>
        <div>
          <a href={REPOSITORY}>{t.footerLinks[0]}</a>
          <a href={`${REPOSITORY}#readme`}>{t.footerLinks[1]}</a>
          <a href={`${REPOSITORY}/releases`}>{t.footerLinks[2]}</a>
          <a href={`${REPOSITORY}/blob/main/SECURITY.md`}>{t.footerLinks[3]}</a>
          <a href={`${REPOSITORY}/blob/main/LICENSE`}>{t.footerLinks[4]}</a>
        </div>
      </footer>
    </main>
  );
}
