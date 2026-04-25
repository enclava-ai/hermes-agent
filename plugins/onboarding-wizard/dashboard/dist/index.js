/**
 * Hermes onboarding wizard — dashboard plugin frontend.
 *
 * Vanilla IIFE that uses upstream's plugin SDK. No build step, no bundler.
 *
 * Maintainability contract with upstream:
 *   - Reads `window.__HERMES_PLUGIN_SDK__` (React, hooks, components, fetchJSON, utils).
 *   - Registers the page via `window.__HERMES_PLUGINS__.register(name, Component)`.
 *   - Backend lives at /api/plugins/onboarding-wizard/*.
 *
 * If upstream changes the SDK in a breaking way, the version-check below will
 * surface a banner instead of crashing silently.
 */
(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !SDK.React) {
    // Bail out loudly — the plugin host should always provide an SDK.
    console.error("Hermes onboarding wizard: __HERMES_PLUGIN_SDK__ missing");
    return;
  }

  // Lock the plugin to the SDK major versions we tested against. Upstream
  // bumps the major when there's a breaking change, so this gate trips
  // before we ship a confusingly broken UI.
  const SDK_MAJOR_TESTED = 1;
  const sdkVersion = String(SDK.version || "1.0.0");
  const sdkMajor = parseInt(sdkVersion.split(".")[0], 10) || 1;
  const sdkMismatch = sdkMajor !== SDK_MAJOR_TESTED;

  const { React } = SDK;
  const { useState, useEffect, useCallback } = SDK.hooks;
  const C = SDK.components || {};
  // Defensive aliases — fall back to plain elements if a component is gone.
  const Card = C.Card || ((props) => React.createElement("div", { className: "border border-border p-4" }, props.children));
  const CardHeader = C.CardHeader || ((p) => React.createElement("div", { className: "mb-3" }, p.children));
  const CardTitle = C.CardTitle || ((p) => React.createElement("h3", { className: "text-base font-semibold" }, p.children));
  const CardContent = C.CardContent || ((p) => React.createElement("div", { className: "flex flex-col gap-3" }, p.children));
  const Button = C.Button || ((p) => React.createElement("button", p, p.children));
  const Input = C.Input || ((p) => React.createElement("input", p));
  const Label = C.Label || ((p) => React.createElement("label", p, p.children));
  const Select = C.Select || null;
  const Badge = C.Badge || ((p) => React.createElement("span", { className: "border px-2 text-xs" }, p.children));
  const Separator = C.Separator || (() => React.createElement("hr", { className: "border-border my-2" }));
  const cn = (SDK.utils && SDK.utils.cn) || ((...xs) => xs.filter(Boolean).join(" "));

  const API = "/api/plugins/onboarding-wizard";

  function fetchJSON(path, opts) {
    if (SDK.fetchJSON) return SDK.fetchJSON(path, opts);
    // Conservative fallback if SDK doesn't expose fetchJSON.
    const headers = Object.assign(
      { "content-type": "application/json" },
      (opts && opts.headers) || {},
    );
    const sessionToken = window.__HERMES_SESSION_TOKEN__;
    if (sessionToken) headers["x-hermes-session"] = sessionToken;
    return fetch(path, Object.assign({}, opts, { headers })).then((r) => {
      if (!r.ok) return r.text().then((t) => { throw new Error(t || r.statusText); });
      return r.json();
    });
  }

  // -------------------------------------------------------------------------
  // Step 1 — LLM provider
  // -------------------------------------------------------------------------

  function LlmStep({ ctx, onSaved, flash, setFlash }) {
    const [provider, setProvider] = useState(ctx.provider || "");
    const [modelName, setModelName] = useState(ctx.model_name || "");
    const [apiKey, setApiKey] = useState("");
    const [apiKeyEnvVar, setApiKeyEnvVar] = useState(ctx.api_key_env_var || "");
    const [temperature, setTemperature] = useState(String(ctx.temperature || ""));
    const [maxTokens, setMaxTokens] = useState(String(ctx.max_tokens || ""));
    const [busy, setBusy] = useState(false);

    // When provider changes, default the env var to the provider's first slot.
    useEffect(() => {
      if (!provider) return;
      const entry = (ctx.providers || []).find((p) => p.name === provider);
      if (entry && entry.env_var) setApiKeyEnvVar(entry.env_var);
    }, [provider]); // eslint-disable-line

    const submit = useCallback(() => {
      setBusy(true);
      setFlash(null);
      fetchJSON(`${API}/llm`, {
        method: "POST",
        body: JSON.stringify({
          provider,
          model_name: modelName,
          api_key: apiKey,
          api_key_env_var: apiKeyEnvVar,
          temperature,
          max_tokens: maxTokens,
        }),
      })
        .then((res) => onSaved(res.draft))
        .catch((err) => setFlash({ type: "error", message: String(err.message || err) }))
        .finally(() => setBusy(false));
    }, [provider, modelName, apiKey, apiKeyEnvVar, temperature, maxTokens, onSaved, setFlash]);

    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, null, "Step 1 — LLM provider"),
      ),
      React.createElement(CardContent, null,
        React.createElement(Field, {
          label: "Provider",
          children: React.createElement("select", {
            className: "border border-border bg-background/40 px-3 py-2 text-sm",
            value: provider,
            onChange: (e) => setProvider(e.target.value),
          },
            React.createElement("option", { value: "" }, "— select —"),
            ...(ctx.providers || []).map((p) =>
              React.createElement("option", { key: p.name, value: p.name }, p.display_name || p.name),
            ),
          ),
        }),
        React.createElement(Field, {
          label: "Model",
          help: "Provider-specific model slug, e.g. claude-sonnet-4.6 or gpt-5",
          children: React.createElement(Input, {
            value: modelName,
            onChange: (e) => setModelName(e.target.value),
            placeholder: "claude-sonnet-4.6",
          }),
        }),
        React.createElement(Field, {
          label: "API key env var",
          children: React.createElement(Input, {
            value: apiKeyEnvVar,
            onChange: (e) => setApiKeyEnvVar(e.target.value),
            placeholder: "ANTHROPIC_API_KEY",
          }),
        }),
        React.createElement(Field, {
          label: "API key",
          help: ctx.api_key_display
            ? `Already saved: ${ctx.api_key_display}. Leave blank to keep.`
            : "Will be written to ~/.hermes/.env",
          children: React.createElement(Input, {
            type: "password",
            value: apiKey,
            onChange: (e) => setApiKey(e.target.value),
            placeholder: "sk-...",
          }),
        }),
        React.createElement("div", { className: "grid grid-cols-2 gap-3" },
          React.createElement(Field, {
            label: "Temperature",
            children: React.createElement(Input, {
              value: temperature,
              onChange: (e) => setTemperature(e.target.value),
              placeholder: "0.7",
            }),
          }),
          React.createElement(Field, {
            label: "Max tokens",
            children: React.createElement(Input, {
              value: maxTokens,
              onChange: (e) => setMaxTokens(e.target.value),
              placeholder: "8192",
            }),
          }),
        ),
        React.createElement("div", { className: "flex justify-end" },
          React.createElement(Button, {
            onClick: submit,
            disabled: busy,
            className: cn(
              "inline-flex items-center gap-2 border border-border bg-foreground/10 px-4 py-2",
              "text-sm font-courier transition-colors hover:bg-foreground/20 cursor-pointer",
            ),
          }, busy ? "Saving..." : "Save & continue →"),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Step 2 — Platform connection
  // -------------------------------------------------------------------------

  function PlatformStep({ ctx, onTested, flash, setFlash }) {
    const [selected, setSelected] = useState(ctx.selected_platform || "");
    const [forms, setForms] = useState({});
    const [busyId, setBusyId] = useState(null);

    const setField = (platformId, name, value) => {
      setForms((prev) => ({
        ...prev,
        [platformId]: { ...(prev[platformId] || {}), [name]: value },
      }));
    };

    const runTest = useCallback((platformId) => {
      setBusyId(platformId);
      setFlash(null);
      fetchJSON(`${API}/test`, {
        method: "POST",
        body: JSON.stringify({
          platform: platformId,
          form_data: forms[platformId] || {},
        }),
      })
        .then((res) => {
          if (res.ok) {
            setSelected(platformId);
            setFlash({ type: "success", message: res.message });
            onTested(res.draft);
          } else {
            setFlash({ type: "error", message: res.message });
          }
        })
        .catch((err) => setFlash({ type: "error", message: String(err.message || err) }))
        .finally(() => setBusyId(null));
    }, [forms, onTested, setFlash]);

    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, null, "Step 2 — Connect a platform"),
      ),
      React.createElement(CardContent, null,
        React.createElement("p", { className: "text-sm text-muted-foreground" },
          "Test at least one platform connection to continue. Credentials are written to ~/.hermes/.env after the wizard completes.",
        ),
        ...(ctx.platforms || []).map((p) =>
          React.createElement(PlatformCard, {
            key: p.id,
            platform: p,
            values: forms[p.id] || {},
            onChange: (name, value) => setField(p.id, name, value),
            onTest: () => runTest(p.id),
            busy: busyId === p.id,
            isSelected: selected === p.id,
          }),
        ),
      ),
    );
  }

  function PlatformCard({ platform, values, onChange, onTest, busy, isSelected }) {
    return React.createElement("div", {
      className: cn(
        "border border-border p-3 flex flex-col gap-2",
        isSelected && "border-foreground/60",
      ),
    },
      React.createElement("div", { className: "flex items-center justify-between" },
        React.createElement("div", { className: "flex items-center gap-2" },
          React.createElement("h4", { className: "font-medium" }, platform.display_name),
          platform.configured && React.createElement(Badge, { variant: "outline" }, "configured"),
          isSelected && React.createElement(Badge, { variant: "outline" }, "✓ tested"),
        ),
        platform.test_supported && React.createElement(Button, {
          onClick: onTest,
          disabled: busy,
          className: cn(
            "border border-border px-3 py-1 text-xs font-courier",
            "hover:bg-foreground/10 cursor-pointer",
          ),
        }, busy ? "Testing..." : "Test"),
      ),
      ...platform.fields.map((f) =>
        React.createElement("div", { key: f.name, className: "flex flex-col gap-1" },
          React.createElement(Label, { className: "text-xs" },
            f.label,
            f.required && React.createElement("span", { className: "text-red-500" }, " *"),
          ),
          React.createElement(Input, {
            type: f.type === "password" ? "password" : "text",
            value: values[f.name] !== undefined ? values[f.name] : (f.value || ""),
            onChange: (e) => onChange(f.name, e.target.value),
            placeholder: f.help || "",
          }),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Step 3 — Summary / Apply
  // -------------------------------------------------------------------------

  function SummaryStep({ draft, onComplete, flash, setFlash }) {
    const [busy, setBusy] = useState(false);

    const apply = useCallback(() => {
      setBusy(true);
      setFlash(null);
      fetchJSON(`${API}/complete`, { method: "POST" })
        .then(() => onComplete())
        .catch((err) => setFlash({ type: "error", message: String(err.message || err) }))
        .finally(() => setBusy(false));
    }, [onComplete, setFlash]);

    const llm = draft.llm || {};
    const platform = draft.platform || {};
    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, null, "Step 3 — Review & apply"),
      ),
      React.createElement(CardContent, null,
        React.createElement(SummaryRow, { label: "Provider", value: llm.provider || "—" }),
        React.createElement(SummaryRow, { label: "Model", value: llm.model_name || "—" }),
        React.createElement(SummaryRow, { label: "Temperature", value: llm.temperature || "default" }),
        React.createElement(SummaryRow, { label: "Max tokens", value: llm.max_tokens || "default" }),
        React.createElement(Separator),
        React.createElement(SummaryRow, {
          label: "Platform",
          value: platform.test_passed
            ? `${platform.selected} (✓ tested)`
            : "(none tested)",
        }),
        React.createElement("p", { className: "text-xs text-muted-foreground" },
          "Clicking apply writes ~/.hermes/config.yaml and ~/.hermes/.env atomically. Your existing keys are preserved unless you overrode them above.",
        ),
        React.createElement("div", { className: "flex justify-end" },
          React.createElement(Button, {
            onClick: apply,
            disabled: busy,
            className: cn(
              "inline-flex items-center gap-2 border border-border bg-foreground/20 px-4 py-2",
              "text-sm font-courier transition-colors hover:bg-foreground/30 cursor-pointer",
            ),
          }, busy ? "Applying..." : "Apply configuration"),
        ),
      ),
    );
  }

  function SummaryRow({ label, value }) {
    return React.createElement("div", { className: "flex justify-between text-sm py-1" },
      React.createElement("span", { className: "text-muted-foreground" }, label),
      React.createElement("span", { className: "font-courier" }, String(value)),
    );
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function Field({ label, help, children }) {
    return React.createElement("div", { className: "flex flex-col gap-1" },
      React.createElement(Label, { className: "text-xs uppercase tracking-wide text-muted-foreground" }, label),
      children,
      help && React.createElement("span", { className: "text-xs text-muted-foreground" }, help),
    );
  }

  function StepBar({ step, completed, onJump }) {
    const labels = ["LLM", "Platform", "Summary"];
    return React.createElement("div", { className: "flex items-center gap-2 text-xs" },
      ...labels.map((label, idx) => {
        const n = idx + 1;
        const done = completed.includes(n);
        const active = step === n;
        return React.createElement(React.Fragment, { key: n },
          React.createElement("button", {
            onClick: () => (done || active) && onJump(n),
            disabled: !done && !active,
            className: cn(
              "border border-border px-3 py-1 font-courier",
              active && "bg-foreground/10",
              done && !active && "opacity-70",
              !done && !active && "opacity-40 cursor-not-allowed",
            ),
          }, `${n}. ${label}`),
          idx < labels.length - 1 && React.createElement("span", {
            className: "text-muted-foreground",
          }, "→"),
        );
      }),
    );
  }

  function Flash({ flash }) {
    if (!flash) return null;
    const tone = flash.type === "error" ? "border-red-500 text-red-500" : "border-green-500 text-green-500";
    return React.createElement("div", {
      className: cn("border px-3 py-2 text-sm font-courier", tone),
    }, flash.message);
  }

  // -------------------------------------------------------------------------
  // Page root
  // -------------------------------------------------------------------------

  function OnboardingWizard() {
    const [state, setState] = useState(null);
    const [step, setStep] = useState(1);
    const [flash, setFlash] = useState(null);
    const [done, setDone] = useState(false);

    const reload = useCallback(() => {
      fetchJSON(`${API}/state`)
        .then((s) => {
          setState(s);
          setStep(s.draft.current_step || 1);
        })
        .catch((err) => setFlash({ type: "error", message: String(err.message || err) }));
    }, []);

    useEffect(reload, [reload]);

    if (!state) {
      return React.createElement("div", { className: "p-6 text-sm text-muted-foreground" }, "Loading wizard…");
    }
    if (state.managed) {
      return React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "Setup wizard disabled"),
        ),
        React.createElement(CardContent, null,
          React.createElement("p", { className: "text-sm text-muted-foreground" },
            "This Hermes installation is managed by an external system. Configuration must be edited via the host's tooling.",
          ),
        ),
      );
    }
    if (done) {
      return React.createElement(Card, null,
        React.createElement(CardHeader, null,
          React.createElement(CardTitle, null, "✓ Setup complete"),
        ),
        React.createElement(CardContent, null,
          React.createElement("p", { className: "text-sm" },
            "Configuration applied to ~/.hermes/config.yaml and ~/.hermes/.env. ",
            "You can re-run the wizard any time to update your settings.",
          ),
          React.createElement(Button, {
            onClick: () => { setDone(false); reload(); },
            className: "border border-border px-3 py-1 text-xs font-courier hover:bg-foreground/10 cursor-pointer self-start",
          }, "Run again"),
        ),
      );
    }

    const completed = (state.draft.completed_steps || []);

    let stepNode = null;
    if (step === 1) {
      stepNode = React.createElement(LlmStep, {
        ctx: state.llm,
        flash, setFlash,
        onSaved: (draft) => { setState({ ...state, draft }); setStep(2); },
      });
    } else if (step === 2) {
      stepNode = React.createElement(PlatformStep, {
        ctx: state.platforms,
        flash, setFlash,
        onTested: (draft) => { setState({ ...state, draft }); },
      });
    } else {
      stepNode = React.createElement(SummaryStep, {
        draft: state.draft,
        flash, setFlash,
        onComplete: () => setDone(true),
      });
    }

    return React.createElement("div", { className: "flex flex-col gap-4 max-w-3xl" },
      sdkMismatch && React.createElement("div", {
        className: "border border-yellow-500 text-yellow-500 px-3 py-2 text-xs font-courier",
      }, `Plugin SDK major version mismatch (built for ${SDK_MAJOR_TESTED}.x, host ${sdkVersion}). The wizard may render incorrectly.`),
      React.createElement(StepBar, {
        step, completed,
        onJump: (n) => {
          if (n === 3 && !completed.includes(2)) {
            setFlash({ type: "error", message: "Test a platform connection before reviewing." });
            return;
          }
          setStep(n);
        },
      }),
      React.createElement(Flash, { flash }),
      stepNode,
      React.createElement("div", { className: "flex justify-between text-xs" },
        step > 1 && React.createElement(Button, {
          onClick: () => setStep(step - 1),
          className: "border border-border px-3 py-1 font-courier hover:bg-foreground/10 cursor-pointer",
        }, "← Back"),
        step === 2 && React.createElement(Button, {
          onClick: () => {
            if (!completed.includes(2)) {
              setFlash({ type: "error", message: "Test a platform connection before continuing." });
              return;
            }
            setStep(3);
          },
          className: "border border-border px-3 py-1 font-courier hover:bg-foreground/10 cursor-pointer ml-auto",
        }, "Continue →"),
      ),
    );
  }

  if (!window.__HERMES_PLUGINS__ || !window.__HERMES_PLUGINS__.register) {
    console.error("Hermes onboarding wizard: __HERMES_PLUGINS__.register missing");
    return;
  }
  window.__HERMES_PLUGINS__.register("onboarding-wizard", OnboardingWizard);
})();
