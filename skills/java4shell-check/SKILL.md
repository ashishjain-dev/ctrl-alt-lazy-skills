---
name: java4shell-check
description: Read-only audit of a repo for Java4Shell (CVE-2026-114938, the OpenJDK Base64 intrinsic bug on AVX-512 VBMI CPUs). Finds every place a Java runtime is chosen (Dockerfiles and base images, CI setup-java, Maven/Gradle toolchains, .java-version, .sdkmanrc, .tool-versions, Kubernetes and Helm image tags, devcontainers), classifies each as AFFECTED / FIXED / NOT AFFECTED / UNKNOWN with file:line, and gives patch targets, the temporary JVM flag and host checks for you to run. Use for "are we exposed to Java4Shell", "which Java do we run", "check CVE-2026-114938".
argument-hint: "[repo paths...] [--include-vendored]"
---

# Java4Shell check

Answer one question with evidence: **where in this codebase could a vulnerable JVM be running, and what exactly should change?**

Arguments: `$ARGUMENTS`

**Read-only.** Never edit files, bump versions, pull images, open PRs or run anything against a server. The user decides and applies the fix. If they ask you to apply it afterwards, that is a separate task: confirm the plan first.

## 0. Facts this skill relies on (re-verify)

Advisories move. Before reporting, re-check these against the OpenJDK vulnerability advisory, your JDK vendor's advisory and NVD for CVE-2026-114938, and say in the report which ones you re-verified and when. If the web is unavailable, say the facts below are as of 2026-11-19.

| Item | As of 2026-11-19 |
|---|---|
| Affected | OpenJDK 17.0.6 and later 17 builds, all 21, 25 and 27 builds **before** the fixed builds below |
| Fixed builds | 17.0.21.1 · 21.0.13.1 · 25.0.5.1 · 27.0.1.1 (vendor names and build suffixes differ, e.g. Temurin, Corretto, Zulu, Red Hat, Microsoft; check each vendor's own advisory) |
| Not affected | Java 8 and 11 (exception: Oracle's Java 8 performance build 8u511b33-perf), and non-x86 CPUs (ARM/aarch64, e.g. Graviton, Apple Silicon) |
| Exploit condition | x86-64 CPU with **AVX-512 VBMI** (newer Intel Xeon and AMD EPYC); the JIT uses the vulnerable Base64 intrinsic only there |
| Temporary mitigation | start the JVM with `-XX:-UseBASE64Intrinsics` (disables the vulnerable path; small Base64 performance cost). Not a substitute for patching |
| Shown exploitable | pre-auth RCE demonstrated on default installs of Jenkins, Jira, Confluence, Keycloak, Artifactory and PingFederate |

A version string alone never proves "safe": a vendor may backport the fix under a different number, and a floating tag (`eclipse-temurin:21-jre`) can resolve to a vulnerable or fixed build depending on when the image was pulled. Treat floating tags as **UNKNOWN** unless pinned by digest and the digest is known.

## 1. Scope

- Repos: paths in `$ARGUMENTS`, else the current repo.
- Skip `node_modules`, `vendor/`, `.git/`, build output (`target/`, `build/`, `dist/`) unless `--include-vendored`.
- Monorepo: report per service (directory that owns a Dockerfile, chart or build file).

## 2. Find every runtime selection (read-only search)

Search with Grep/Glob, then read the matching lines. Record `file:line`, the raw value and what it controls.

| Where | What to look for |
|---|---|
| Container images | `FROM` lines in `Dockerfile*`, `Containerfile*` (all stages; the **final** stage is the runtime). `eclipse-temurin`, `amazoncorretto`, `azul/zulu-openjdk`, `openjdk`, `ibm-semeru`, `bellsoft/liberica`, `mcr.microsoft.com/openjdk`, `registry.access.redhat.com/ubi*/openjdk-*`, `gcr.io/distroless/java*`, `jenkins/jenkins`, `atlassian/*`, `keycloak/keycloak`, `releases-docker.jfrog.io/*artifactory*` |
| Build-time JDK installs | `apt-get install openjdk-*`, `apk add openjdk*`, `yum/dnf install java-*`, `sdk install java`, curl/wget of JDK tarballs |
| Jib / Buildpacks | `jib.from.image` in `pom.xml` / `build.gradle(.kts)`; `BP_JVM_VERSION` in `project.toml` or CI env |
| CI | `actions/setup-java` (`java-version`, `distribution`), GitLab `image:`, Jenkinsfile `tools { jdk }` / `agent { docker }`, CircleCI `cimg/openjdk`, Azure `JavaToolInstaller` |
| Build toolchains | Maven `maven.compiler.release` / `<release>` (compile target only, not the runtime), `maven-toolchains-plugin`, Gradle `java { toolchain { languageVersion } }`, `.mvn/jvm.config` |
| Version pins | `.java-version`, `.sdkmanrc`, `.tool-versions`, `.devcontainer/devcontainer.json` features, `mise.toml` |
| Deploy | Kubernetes manifests, Helm `values*.yaml` (`image.repository` / `tag`), Kustomize `images:`, docker-compose, ECS task definitions, Terraform image vars |
| JVM flags | `JAVA_TOOL_OPTIONS`, `JDK_JAVA_OPTIONS`, `JAVA_OPTS`, `ENTRYPOINT`/`CMD` with `java`, Helm `jvmOptions`; note whether `-XX:-UseBASE64Intrinsics` is already set |
| Architecture | `--platform`, `platform:` in compose, `nodeSelector`/`affinity` on `kubernetes.io/arch`, instance types in Terraform (Graviton `*g.*` = ARM) |

Label inferences as inferences ("final stage looks like the runtime because it holds the `ENTRYPOINT`").

## 3. Classify each finding

- **AFFECTED**: a pinned version inside the affected range on x86-64 (or arch unknown).
- **FIXED**: a pinned version at or above the fixed build for its line, or a vendor build named fixed in that vendor's advisory.
- **NOT AFFECTED**: Java 8 or 11 (not the 8u511b33-perf build), or pinned to ARM only. Say why.
- **UNKNOWN**: floating tag, `latest`, version from a variable you cannot resolve, a third-party product image (Jenkins, Atlassian, Keycloak, Artifactory) whose bundled JDK you cannot see from the repo.
- Compile target ≠ runtime: `<release>17</release>` says what bytecode is produced, not which JVM runs it. Never classify on it alone; use it only to say which fixed line to move to.

Mitigation present (`-XX:-UseBASE64Intrinsics` set on that runtime): keep the class, add "mitigated".

## 4. Priority

Order findings by blast radius, highest first:

1. Internet-facing services and the products named in section 0 (Jenkins, Jira, Confluence, Keycloak, Artifactory, PingFederate), and anything that decodes untrusted Base64 (auth tokens, JWTs, SAML, webhooks).
2. Internal services on x86 with AVX-512-capable instance types.
3. CI runners and build agents.
4. Local dev tooling.

## 5. Commands for the user to run (do not run them yourself)

Give these per affected or unknown runtime, filled in with the real image or host:

```bash
# What the runtime really is (the image tag can lie)
docker run --rm --entrypoint java <image@digest-or-tag> -version
kubectl exec <pod> -- java -version

# Does this host have AVX-512 VBMI? (x86 Linux)
grep -o -m1 'avx512vbmi' /proc/cpuinfo || echo "no avx512vbmi"
kubectl exec <pod> -- grep -o -m1 avx512vbmi /proc/cpuinfo

# Is the mitigation flag active in a running JVM?
jcmd <pid> VM.flags | tr ' ' '\n' | grep -i Base64Intrinsics
```

## 6. Output format (fixed)

```
JAVA4SHELL CHECK · <repo> · facts as of <date, re-verified: yes/no>

VERDICT: EXPOSED | LIKELY EXPOSED | NOT EXPOSED IN REPO | CAN'T TELL
<one line why>

| # | Status | Where (file:line) | Runtime found | Arch | Why |
|---|---|---|---|---|---|
| 1 | AFFECTED | deploy/api/Dockerfile:14 | eclipse-temurin:17.0.12_7-jre | x86 (default) | 17.0.12 < 17.0.21.1 |
...

FIX (per finding, highest priority first)
1. deploy/api/Dockerfile:14 → move to the vendor's fixed 17.0.21.1 build (pin by digest).
   Can't redeploy today: add -XX:-UseBASE64Intrinsics via JAVA_TOOL_OPTIONS in <file:line>.

RUN THESE (you, not me)
<commands from section 5, filled in>

NOT CHECKED
<anything outside the repo: running hosts, base images pulled earlier, vendor appliances>
```

Rules for the report: no finding without `file:line`; no "you're safe" from a version string alone; say what you could not see. Keep it under one screen when possible.
