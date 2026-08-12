"use client";

/* eslint-disable @next/next/no-img-element */
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

const copy = {
  en: {
    nav: ["Product", "Audit loop", "Research", "Security"],
    docs: "Docs",
    download: "Download",
    eyebrow: "LOCAL-FIRST AGENT · INDEPENDENT AUDIT",
    titleA: "Build with an agent.",
    titleB: "Ship with evidence.",
    intro: "Two independent models create, challenge, and trace every result before you approve it.",
    heroFacts: [
      ["2 providers", "Separated creation and review"],
      ["Git-backed", "Every accepted revision is traceable"],
      ["Human gate", "You control final admission"],
    ],
    interfaceStatus: "Local workspace · live audit state",
    primaryCta: "Download macOS",
    sourceCta: "View GitHub",
    realInterface: "The current CrossAudit workspace, running locally on macOS.",
    statement: "One model builds. Another model checks.",
    statementBody:
      "CrossAudit separates creation from judgment. The auditor sees committed work, not the generator's private reasoning.",
    signalFacts: [
      ["LOCAL", "Files and audit history stay in folders you choose"],
      ["PAIRED", "Creation and review use independent providers"],
      ["LIVE", "Every run state reaches the workspace in real time"],
      ["GIT", "Candidates and revisions remain inspectable"],
      ["EXTENSIBLE", "MCP, skills, GitHub, and bounded HPC"],
      ["FAIL-CLOSED", "Failure pauses the run instead of approving it"],
    ],
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
    flowSatellites: [["FILES", "Input and output"], ["MCP + SKILLS", "Scoped tools"], ["HPC", "Remote compute"], ["GITHUB", "Paired repositories"]],
    flowOutcomes: [["PASS", "Admission path"], ["BLOCK", "Revision loop"], ["ESCALATE", "Human decision"]],
    flowBoundary: "The auditor sees committed work, not the generator's private chain of thought.",
    flowInstruction: "Scroll or select a node",
    generator: "Generator",
    auditor: "Auditor",
    controller: "CrossAudit",
    active: "Current state",
    actualProduct: "A real product, not a concept render.",
    actualProductBody:
      "Projects, chats, providers, files, audit context, and human handoff live in one native macOS workspace.",
    screenshotCaption: "A live project conversation with independent audit context visible on demand.",
    openFullSize: "Open full-resolution image",
    resultTitle: "Results stay simple. Evidence stays available.",
    resultBody:
      "Users receive the file they asked for. Audit details remain one deliberate action deeper, ready for inspection without cluttering the work.",
    resultPoints: ["Direct file output", "Built-in preview", "Human-readable findings", "Durable receipt"],
    workbenchTitle: "One workspace from first prompt to verified output.",
    workbenchBody:
      "The conversation remains primary. Files, model activity, findings, and the admission decision stay close enough to inspect without becoming the interface.",
    depthTitle: "Start in minutes. Go as deep as the work demands.",
    beginner: "First project",
    beginnerBody: "Choose a folder, connect two providers, and describe the result you need.",
    engineering: "Software work",
    engineeringBody: "Keep revisions in Git. Add MCP tools. Admit only the result that passes.",
    research: "Research and HPC",
    researchBody:
      "Submit bounded remote jobs, follow logs, and return declared results into the same audit loop.",
    safetyTitle: "Failure never turns into approval.",
    safetyBody:
      "A crashed worker, exhausted budget, provider outage, or unresolved blocker pauses the task and asks for a specific decision.",
    safetyItems: ["Provider recovery", "Crash recovery", "Budget boundary", "Human decision"],
    capabilityTitle: "More capability, without a busier interface.",
    capabilityBody:
      "CrossAudit reveals depth when the task needs it. The same workspace can remain simple for a first project or expand into engineering and scientific work.",
    capabilityItems: [
      ["Files in and out", "Drop source files, preview results, and export only the deliverables you asked for."],
      ["Models and effort", "Switch providers, models, and supported reasoning effort without rebuilding a project."],
      ["Tools and skills", "Connect MCP servers and reusable skills with explicit project scope."],
      ["Remote compute", "Submit bounded HPC jobs, follow logs, and return declared outputs to the audit loop."],
      ["Durable projects", "Choose local folders, keep Git history, and connect purpose-specific GitHub repositories."],
      ["Safe recovery", "Provider failure, budget exhaustion, or a blocked review pauses for an understandable decision."],
    ],
    securityTitle: "Local work. Explicit connections.",
    securityBody:
      "Projects and audit history live in folders you choose. API keys stay write-only in the macOS Keychain. GitHub, MCP, and HPC actions use scoped permissions.",
    local: "On your Mac",
    localBody: "Project files, Git history, receipts, and local runtime state.",
    connected: "Only when you connect it",
    connectedBody: "Model providers, GitHub repositories, MCP servers, and remote compute.",
    releaseEyebrow: "LATEST RELEASE",
    releaseTitle: "Download from the source.",
    releaseBody: "The installer and checksum come directly from the official GitHub release.",
    loading: "Checking the latest GitHub release",
    live: "Latest stable release confirmed by GitHub",
    fallback: "GitHub API is unavailable. The official latest-release link remains available.",
    checksum: "Get checksum",
    notes: "Read release notes",
    size: "Installer size",
    integrity:
      "This community build is ad-hoc signed and not Apple-notarized. macOS may ask you to confirm its first launch.",
    finalTitle: "Trust work you can inspect.",
    finalBody: "Create with an agent. Keep the evidence. Decide for yourself.",
    github: "GitHub",
    testReport: "Test report",
    footer: "Open source software for inspectable AI work.",
  },
  zh: {
    nav: ["产品", "审计循环", "科研", "安全"],
    docs: "文档",
    download: "下载",
    eyebrow: "本地优先 AGENT · 独立审计",
    titleA: "让 Agent 创作。",
    titleB: "让证据决定交付。",
    intro: "两个独立模型创建、质疑并追溯每个结果，再由你决定是否批准。",
    heroFacts: [
      ["2 个厂商", "创作与审查相互分离"],
      ["Git 追溯", "每个被接受的修订均有记录"],
      ["人工准入", "最终交付由你决定"],
    ],
    interfaceStatus: "本地工作区 · 审计状态实时更新",
    primaryCta: "下载 macOS 版",
    sourceCta: "查看 GitHub",
    realInterface: "目前真实运行在 macOS 本地的 CrossAudit 工作区。",
    statement: "一个模型完成工作，另一个模型检查结果。",
    statementBody: "CrossAudit 将创作与判断分开。审计者看到已提交的工作，而不是生成者的私有推理。",
    signalFacts: [
      ["本地", "文件与审计历史保存在你选择的文件夹"],
      ["双厂商", "创作与审查使用相互独立的模型厂商"],
      ["实时", "每个运行状态都会实时进入工作区"],
      ["Git", "候选结果和修订始终可检查"],
      ["可扩展", "MCP、Skills、GitHub 与有边界的 HPC"],
      ["失败关闭", "发生故障时暂停，而不是错误批准"],
    ],
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
    flowSatellites: [["文件", "输入与输出"], ["MCP + SKILLS", "限定工具"], ["HPC", "远程计算"], ["GITHUB", "双仓库"]],
    flowOutcomes: [["PASS", "进入准入"], ["BLOCK", "返回修订"], ["ESCALATE", "人工决定"]],
    flowBoundary: "审计者看到已提交结果，而不是生成者的私有思维链。",
    flowInstruction: "滚动或选择节点",
    generator: "生成者",
    auditor: "审计者",
    controller: "CrossAudit",
    active: "当前状态",
    actualProduct: "这是真实产品，不是概念渲染。",
    actualProductBody: "项目、对话、模型、文件、审计上下文和人工接管都在一个原生 macOS 工作区中。",
    screenshotCaption: "真实项目对话，独立审计上下文可按需展开。",
    openFullSize: "打开全分辨率图片",
    resultTitle: "结果保持简单，证据始终可查。",
    resultBody: "用户直接得到所需文件。审计详情保留在下一层，需要时随时检查，不干扰主要工作。",
    resultPoints: ["直接文件输出", "内置预览", "易懂的问题说明", "持久审计凭证"],
    workbenchTitle: "从第一条指令到可验证输出，都在同一个工作区。",
    workbenchBody: "对话始终是主界面。文件、模型活动、审计发现和准入决定保持随时可查，但不会挤占主要工作。",
    depthTitle: "几分钟即可开始，也能随工作需求不断深入。",
    beginner: "第一个项目",
    beginnerBody: "选择文件夹，连接两个厂商，然后描述你要的结果。",
    engineering: "软件工程",
    engineeringBody: "使用 Git 保存修订，接入 MCP 工具，只准入真正通过的结果。",
    research: "科研与 HPC",
    researchBody: "提交受约束的远程任务、跟踪日志，并把声明的结果送回同一审计循环。",
    safetyTitle: "失败永远不会被转换成通过。",
    safetyBody: "进程崩溃、预算耗尽、厂商故障或未解决问题都会暂停任务，并请求一个明确决定。",
    safetyItems: ["厂商恢复", "崩溃恢复", "预算边界", "人工决定"],
    capabilityTitle: "能力更完整，界面不必更复杂。",
    capabilityBody: "CrossAudit 只在任务需要时展开深度。同一个工作区既能服务第一次使用，也能扩展到工程和科研任务。",
    capabilityItems: [
      ["文件输入与输出", "拖入源文件、预览结果，并且只导出用户真正需要的交付物。"],
      ["模型与推理强度", "在项目中切换厂商、模型和受支持的推理强度，无需重新创建项目。"],
      ["工具与 Skills", "以明确的项目范围连接 MCP 服务和可复用 Skills。"],
      ["远程计算", "提交有边界的 HPC 任务、跟踪日志，并将声明的输出送回审计循环。"],
      ["持久项目", "选择本地文件夹、保留 Git 历史，并连接用途明确的 GitHub 仓库。"],
      ["安全恢复", "厂商故障、预算耗尽或审查阻塞都会暂停，并请求一个易懂的决定。"],
    ],
    securityTitle: "工作留在本地，连接始终明确。",
    securityBody: "项目与审计历史保存在你选择的文件夹。API 密钥以只写方式存入 macOS 钥匙串。GitHub、MCP 与 HPC 使用范围明确的权限。",
    local: "在你的 Mac 上",
    localBody: "项目文件、Git 历史、凭证和本地运行状态。",
    connected: "只在你主动连接后",
    connectedBody: "模型厂商、GitHub 仓库、MCP 服务器和远程计算。",
    releaseEyebrow: "最新版本",
    releaseTitle: "直接从源头下载。",
    releaseBody: "安装包和校验文件均直接来自官方 GitHub Release。",
    loading: "正在检查 GitHub 最新版本",
    live: "已通过 GitHub 确认最新稳定版本",
    fallback: "GitHub API 暂时不可用，官方最新版本链接仍可访问。",
    checksum: "获取校验文件",
    notes: "阅读版本说明",
    size: "安装包大小",
    integrity: "此社区构建采用临时签名，尚未通过 Apple 公证。macOS 可能要求你确认首次启动。",
    finalTitle: "信任你能够检查的工作。",
    finalBody: "让 Agent 创作，保留证据，然后由你决定。",
    github: "GitHub",
    testReport: "测试报告",
    footer: "为可检查的 AI 工作而构建的开源软件。",
  },
} as const;

function formatBytes(bytes: number) {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

export function CrossAuditLanding() {
  const [language, setLanguage] = useState<Language>("en");
  const [release, setRelease] = useState<ReleaseInfo>(FALLBACK_RELEASE);
  const [releaseState, setReleaseState] = useState<"loading" | "live" | "fallback">("loading");
  const [auditState, setAuditState] = useState(0);
  const flowRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const element = flowRef.current;
    if (!element) return;
    const chapters = Array.from(element.querySelectorAll<HTMLElement>("[data-flow-step]"));
    if (reduceMotion.matches) return;
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

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (reduceMotion.matches) {
      elements.forEach((element) => element.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8%", threshold: 0.12 },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
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

      <header className="site-header">
        <a className="brand" href="#top" aria-label="CrossAudit home">
          <BrandMark />
          <span>CrossAudit</span>
        </a>
        <nav className="desktop-nav">
          {t.nav.map((item, index) => (
            <a key={item} href={["#top", "#audit", "#capabilities", "#security"][index]}>
              {item}
            </a>
          ))}
          <a href={`${REPOSITORY}#readme`}>{t.docs}</a>
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
          <a className="header-download" href="#download">{t.download}</a>
        </div>
      </header>

      <div id="main-content">
        <section className="hero section-shell" id="top">
          <div className="hero-copy">
            <p className="eyebrow">{t.eyebrow}</p>
            <h1><span>{t.titleA}</span><span className="accent-line">{t.titleB}</span></h1>
            <p className="hero-intro">{t.intro}</p>
            <div className="hero-actions">
              <a className="button button-primary" href={assets.dmg?.browser_download_url ?? RELEASES}>{t.primaryCta}</a>
              <a className="button button-secondary" href={REPOSITORY}>{t.sourceCta}</a>
            </div>
          </div>
          <figure className="hero-visual">
            <div className="capture-frame">
              <a className="capture-link" href="/crossaudit-workspace.png" target="_blank" rel="noreferrer" aria-label={t.openFullSize}>
                <img
                  src="/crossaudit-workspace-1600.png"
                  srcSet="/crossaudit-workspace-960.png 960w, /crossaudit-workspace-1600.png 1600w, /crossaudit-workspace.png 2704w"
                  sizes="(max-width: 72rem) calc(100vw - 4rem), min(56vw, 52rem)"
                  width={2704}
                  height={1824}
                  fetchPriority="high"
                  decoding="async"
                  alt={t.realInterface}
                />
              </a>
              <span className="capture-status"><i aria-hidden="true" />{t.interfaceStatus}</span>
            </div>
            <figcaption>{t.realInterface} <a href="/crossaudit-workspace.png" target="_blank" rel="noreferrer">{t.openFullSize}</a></figcaption>
          </figure>
        </section>

        <section className="signal-strip section-shell" id="product" data-reveal>
          <div>
            <h2>{t.statement}</h2>
            <p>{t.statementBody}</p>
          </div>
          <div className="signal-list">
            {t.signalFacts.map(([value, label]) => <span key={value}><b>{value}</b>{label}</span>)}
          </div>
        </section>

        <section className="audit-section section-shell" id="audit">
          <div className="section-heading" data-reveal>
            <h2>{t.auditTitle}</h2>
            <p>{t.auditBody}</p>
          </div>
          <div className="flow-scroll-layout" ref={flowRef}>
            <div className="flow-map-sticky" data-reveal role="region" aria-label={t.auditTrace}>
              <div className="flow-map-head">
                <div><i aria-hidden="true" /><span>{t.auditTrace}</span></div>
                <span>{t.auditRound}</span>
              </div>
              <div className="flow-canvas">
                <div className="flow-satellites" role="group" aria-label={language === "zh" ? "扩展能力" : "Connected capabilities"}>
                  {t.flowSatellites.map(([title, body]) => <span key={title}><strong>{title}</strong><small>{body}</small></span>)}
                </div>
                <div className="flow-main-nodes">
                  {t.flowSteps.slice(0, 6).map(([title, role], index) => (
                    <button
                      type="button"
                      className={`flow-node ${auditState === index ? "active" : ""} ${auditState > index ? "reached" : ""}`}
                      aria-pressed={auditState === index}
                      onClick={() => setAuditState(index)}
                      key={title}
                    >
                      <span>0{index + 1}</span><strong>{title}</strong><small>{role}</small>
                    </button>
                  ))}
                </div>
                <div className="flow-branch" aria-hidden="true"><i /><i /><i /></div>
                <div className="flow-branch-nodes">
                  {t.flowSteps.slice(6).map(([title, role], localIndex) => {
                    const index = localIndex + 6;
                    return (
                      <button
                        type="button"
                        className={`flow-node ${auditState === index ? "active" : ""} ${auditState > index ? "reached" : ""}`}
                        aria-pressed={auditState === index}
                        onClick={() => setAuditState(index)}
                        key={title}
                      >
                        <span>0{index + 1}</span><strong>{title}</strong><small>{role}</small>
                      </button>
                    );
                  })}
                </div>
                <div className="flow-outcomes">
                  {t.flowOutcomes.map(([title, body], index) => (
                    <span className={auditState === 6 || (auditState === 7 && index === 0) ? "active" : ""} key={title}>
                      <strong>{title}</strong><small>{body}</small>
                    </span>
                  ))}
                </div>
              </div>
              <div className="flow-detail" aria-live="polite" key={`${language}-${auditState}`}>
                <div className="flow-detail-index"><span>0{auditState + 1}</span><small>{t.flowInstruction}</small></div>
                <div className="flow-detail-copy">
                  <p>{t.flowSteps[auditState][1]}</p>
                  <h3>{t.flowSteps[auditState][0]}</h3>
                  <span>{t.flowSteps[auditState][2]}</span>
                </div>
                <div className="flow-evidence"><span>{t.evidenceLabel}</span><strong>{t.flowSteps[auditState][3]}</strong></div>
              </div>
              <p className="flow-boundary">{t.flowBoundary}</p>
            </div>
            <div className="flow-chapters">
              {t.flowSteps.map(([title, role, body, evidence], index) => (
                <article className={auditState === index ? "active" : ""} data-flow-step={index} aria-current={auditState === index ? "step" : undefined} key={title}>
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
          <div className="workbench-proof" data-reveal>
            <figure className="product-capture">
              <a className="capture-link" href="/crossaudit-audit.png" target="_blank" rel="noreferrer" aria-label={t.openFullSize}>
                <img
                  src="/crossaudit-audit-1600.png"
                  srcSet="/crossaudit-audit-960.png 960w, /crossaudit-audit-1600.png 1600w, /crossaudit-audit.png 2704w"
                  sizes="(max-width: 72rem) calc(100vw - 4rem), min(68vw, 64rem)"
                  width={2704}
                  height={1824}
                  loading="lazy"
                  decoding="async"
                  alt={t.screenshotCaption}
                />
              </a>
              <figcaption>{t.screenshotCaption} <a href="/crossaudit-audit.png" target="_blank" rel="noreferrer">{t.openFullSize}</a></figcaption>
            </figure>
            <div className="workbench-copy">
              <p className="eyebrow">{t.actualProduct}</p>
              <h3>{t.workbenchTitle}</h3>
              <p>{t.workbenchBody}</p>
              <div className="output-list">
                {t.resultPoints.map((point) => <span key={point}>{point}</span>)}
              </div>
            </div>
          </div>
        </section>

        <section className="capability-section section-shell" id="capabilities">
          <div className="section-heading capability-heading" data-reveal>
            <h2>{t.capabilityTitle}</h2>
            <p>{t.capabilityBody}</p>
          </div>
          <div className="capability-grid" data-reveal>
            {t.capabilityItems.map(([title, body], index) => (
              <article className={`capability-item capability-${index + 1}`} key={title}>
                <span>0{index + 1}</span><h3>{title}</h3><p>{body}</p>
              </article>
            ))}
          </div>
          <div className="depth-rail" id="research" data-reveal>
            <article><span>01</span><div><h3>{t.beginner}</h3><p>{t.beginnerBody}</p></div></article>
            <article><span>02</span><div><h3>{t.engineering}</h3><p>{t.engineeringBody}</p></div></article>
            <article><span>03</span><div><h3>{t.research}</h3><p>{t.researchBody}</p></div></article>
          </div>
        </section>

        <section className="boundary-section section-shell" id="security">
          <div className="safety-block" data-reveal>
            <div>
              <h2>{t.safetyTitle}</h2>
              <p>{t.safetyBody}</p>
            </div>
            <div className="safety-list">
              {t.safetyItems.map((item) => <span key={item}><i aria-hidden="true" />{item}</span>)}
            </div>
          </div>
          <div className="security-block" data-reveal>
            <div>
              <p className="eyebrow">{t.securityTitle}</p>
              <p>{t.securityBody}</p>
            </div>
            <div className="boundary-pair">
              <article><span>LOCAL</span><h3>{t.local}</h3><p>{t.localBody}</p></article>
              <article><span>SCOPED</span><h3>{t.connected}</h3><p>{t.connectedBody}</p></article>
            </div>
          </div>
        </section>

        <section className="download-section section-shell" id="download" data-reveal>
          <div className="download-intro">
            <p className="eyebrow">{t.releaseEyebrow}</p>
            <h2>{t.releaseTitle}</h2>
            <p>{t.releaseBody}</p>
            <div className="final-copy">
              <BrandMark />
              <div><strong>{t.finalTitle}</strong><span>{t.finalBody}</span></div>
            </div>
          </div>
          <div className="download-panel">
            <div className="release-version"><span>CrossAudit</span><strong>{releaseVersion}</strong></div>
            <p className={`release-state ${releaseState}`} role="status">
              {releaseState === "loading" ? t.loading : releaseState === "live" ? t.live : t.fallback}
            </p>
            <div className="download-actions">
              <a className="button button-primary" href={assets.dmg?.browser_download_url ?? RELEASES}>{t.primaryCta}</a>
              <a className="button button-secondary" href={assets.checksum?.browser_download_url ?? release.html_url}>{t.checksum}</a>
            </div>
            {assets.dmg ? <p className="download-size">{t.size}: {formatBytes(assets.dmg.size)}</p> : null}
            <a className="release-notes" href={release.html_url}>{t.notes}</a>
            <p className="integrity-note">{t.integrity}</p>
          </div>
        </section>
      </div>

      <footer>
        <div className="footer-brand"><BrandMark /><span>CrossAudit</span></div>
        <p>{t.footer}</p>
        <div>
          <a href={REPOSITORY}>{t.github}</a>
          <a href={`${REPOSITORY}/blob/main/docs/ENTERPRISE_TEST_REPORT.md`}>{t.testReport}</a>
          <a href={`${REPOSITORY}#readme`}>{t.docs}</a>
        </div>
      </footer>
    </main>
  );
}
