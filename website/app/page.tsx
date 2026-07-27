import { CopyProxyButton, DASHBOARD_URL, GITHUB_URL } from "@/components/CopyProxyButton";

const btnPrimary =
  "inline-flex items-center justify-center rounded border border-[#2a5c42] bg-[#1a3d2c] px-5 py-2.5 font-mono text-sm text-accent transition hover:bg-[#214a36]";
const btnGhost =
  "inline-flex items-center justify-center rounded border border-line bg-panel2 px-5 py-2.5 font-mono text-sm text-ink transition hover:border-[#2a3b52]";

export default function HomePage() {
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-5 pb-16 pt-10 md:px-8">
      <header className="mb-16 flex items-center justify-between gap-4 border-b border-line pb-4 font-mono text-xs text-muted">
        <span className="text-accent">ai-attestation</span>
        <span>MIT · open core</span>
      </header>

      {/* Hero */}
      <section className="mb-24" aria-labelledby="hero-title">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.2em] text-muted">
          evidence chain · audit proxy
        </p>
        <h1
          id="hero-title"
          className="max-w-3xl text-3xl font-semibold leading-tight tracking-tight text-ink md:text-5xl md:leading-[1.15]"
        >
          每一次 AI 调用，都应留下可独立验证的证据。
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-[#9eb2c7] md:text-lg">
          不是监控。不是黑箱日志。而是开源审计代理：用防篡改证据链记录 API
          行为，任何人都可以独立校验。
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a className={btnPrimary} href={DASHBOARD_URL}>
            免费试用
          </a>
          <a className={btnGhost} href={GITHUB_URL} target="_blank" rel="noreferrer">
            查看开源代码
          </a>
        </div>
        <p className="mt-6 font-mono text-xs text-muted">
          已适配 12 家AI厂商。核心永远开源。MIT许可证。
        </p>
      </section>

      {/* Problem */}
      <section className="mb-24 border-t border-line pt-16" aria-labelledby="problem-title">
        <h2 id="problem-title" className="text-2xl font-semibold text-ink md:text-3xl">
          AI 行业的信任缺口，正在被当作“正常”。
        </h2>
        <div className="mt-8 grid gap-4 font-mono text-sm leading-relaxed text-[#9eb2c7]">
          <p className="rounded border border-line bg-panel p-4">
            <span className="text-accent">[01]</span>{" "}
            黑箱日志堆在厂商控制台里——看得见摘要，核验不了原始调用。
          </p>
          <p className="rounded border border-line bg-panel p-4">
            <span className="text-accent">[02]</span>{" "}
            账单对不上行为：钱花了，证据链却断在「请信任我们」四个字上。
          </p>
          <p className="rounded border border-line bg-panel p-4">
            <span className="text-accent">[03]</span>{" "}
            当 xAI 被曝违规上传用户代码时，公众只能等到当事人认错才知情——若他不认错，独立第三方拿不出可复现的证据。
          </p>
          <p className="rounded border border-line bg-panel p-4">
            <span className="text-accent">[04]</span>{" "}
            合规声明停在白皮书页。没有可执行检查，就没有可对外出示的审计证据。
          </p>
        </div>
      </section>

      {/* Solution */}
      <section className="mb-24 border-t border-line pt-16" aria-labelledby="solution-title">
        <h2 id="solution-title" className="mb-8 text-2xl font-semibold text-ink md:text-3xl">
          接入审计代理。核验每一次调用。固化每一份证据。
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          <article className="rounded border border-line bg-panel p-5">
            <p className="font-mono text-xs uppercase tracking-wider text-accent">01 · 审计代理</p>
            <h3 className="mt-3 text-lg font-medium text-ink">
              一行接入，所有行为写入证据链。
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              把 API 指向审计代理。连接建立后，调用自动记入哈希链——无需改业务代码。
            </p>
          </article>
          <article className="rounded border border-line bg-panel p-5">
            <p className="font-mono text-xs uppercase tracking-wider text-accent">02 · 哈希链</p>
            <h3 className="mt-3 text-lg font-medium text-ink">
              每一次调用，都在链上留下可核验的一环。
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              SHA-256 哈希链构成防篡改证据。逐环校验每一份报告——断裂即可见。
            </p>
          </article>
          <article className="rounded border border-line bg-panel p-5">
            <p className="font-mono text-xs uppercase tracking-wider text-accent">03 · 独立验证</p>
            <h3 className="mt-3 text-lg font-medium text-ink">
              信任来自可被复现的证据，而非口头声明。
            </h3>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              证据可离线复验。任何人都能打开验证页，核对报告哈希与链完整性。
            </p>
          </article>
        </div>
      </section>

      {/* Climax */}
      <section
        className="mb-24 border border-accent/30 bg-[#0f1a14] px-6 py-12 text-center md:px-12"
        aria-labelledby="climax-title"
      >
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.18em] text-accent">
          verify independently
        </p>
        <h2
          id="climax-title"
          className="mx-auto max-w-2xl text-2xl font-semibold leading-snug text-ink md:text-3xl"
        >
          不可篡改的信任，来自可被任何人复现的证据。
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-sm leading-relaxed text-[#9eb2c7]">
          我们不要求你相信我们。我们要求证据链能被独立复现——证据越可公开校验，结论越稳固。
        </p>
      </section>

      {/* CTA */}
      <section
        className="rounded border border-line bg-panel px-6 py-10 md:px-10"
        aria-labelledby="cta-title"
      >
        <h2 id="cta-title" className="text-2xl font-semibold text-ink">
          先看见，再付钱。
        </h2>
        <p className="mt-3 max-w-xl text-sm text-[#9eb2c7]">
          复制审计代理 URL 接入流量；或打开仓库，阅读协议与实现。规格与定价以文档纯文本为准。
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <CopyProxyButton className={btnPrimary} />
          <a className={btnGhost} href={GITHUB_URL} target="_blank" rel="noreferrer">
            查看 GitHub 仓库
          </a>
          <a className={btnGhost} href={DASHBOARD_URL}>
            打开演示仪表盘
          </a>
        </div>
      </section>

      <footer className="mt-16 border-t border-line pt-6 font-mono text-[11px] text-muted">
        开源宣传站 · ai-attestation
      </footer>
    </main>
  );
}
