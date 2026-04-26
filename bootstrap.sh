#!/usr/bin/env bash
# Sebastian one-line installer.
# Usage: curl -fsSL https://raw.githubusercontent.com/PhantomButler/Sebastian/main/bootstrap.sh | bash
set -euo pipefail

REPO="PhantomButler/Sebastian"
INSTALL_DIR="${SEBASTIAN_INSTALL_DIR:-$HOME/.sebastian/app}"

color_red() { printf "\033[31m%s\033[0m\n" "$*"; }
color_grn() { printf "\033[32m%s\033[0m\n" "$*"; }
color_ylw() { printf "\033[33m%s\033[0m\n" "$*"; }

cat <<'BANNER'
============================================
  Sebastian 一键安装脚本
  动作清单：
    1. 检查系统依赖
    2. 从 GitHub 获取最新 release 信息
    3. 下载 sebastian-backend-<ver>.tar.gz 与 SHA256SUMS
    4. 校验 SHA256 指纹
    5. 检查目标目录（非空时拒绝覆盖）
    6. 解压到 $INSTALL_DIR
    7. 运行 ./scripts/install.sh（venv + 依赖 + 首启向导）
  按 Ctrl+C 随时中止
============================================
BANNER

# 1. 依赖检查
for cmd in curl tar shasum python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    color_red "❌ 缺少依赖命令: $cmd"
    exit 1
  fi
done
color_grn "✓ 系统依赖齐全"

# 2. 最新 release tag
# 走 github.com 的 /releases/latest 302 重定向，避免 api.github.com 的 60/hr 未认证限流
color_ylw "→ 查询最新 release..."
LATEST_LOCATION="$(curl -fsSIL -o /dev/null -w '%{url_effective}' "https://github.com/${REPO}/releases/latest")"
LATEST_TAG="${LATEST_LOCATION##*/}"
if [[ -z "$LATEST_TAG" || "$LATEST_TAG" == "latest" ]]; then
  color_red "❌ 无法解析最新 release tag（从 ${LATEST_LOCATION}）"
  exit 1
fi
color_grn "✓ 最新版本: $LATEST_TAG"

TAR_NAME="sebastian-backend-${LATEST_TAG}.tar.gz"
TAR_URL="https://github.com/${REPO}/releases/download/${LATEST_TAG}/${TAR_NAME}"
SUMS_URL="https://github.com/${REPO}/releases/download/${LATEST_TAG}/SHA256SUMS"

# 3. 下载到临时目录
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

color_ylw "→ 下载 $TAR_NAME ..."
curl -fsSL "$TAR_URL" -o "${TMPDIR}/${TAR_NAME}"
color_ylw "→ 下载 SHA256SUMS ..."
curl -fsSL "$SUMS_URL" -o "${TMPDIR}/SHA256SUMS"

# 4. 校验
color_ylw "→ 校验 SHA256 指纹..."
(
  cd "$TMPDIR"
  shasum -a 256 -c SHA256SUMS --ignore-missing 2>&1 | grep -E "^${TAR_NAME}: OK$" >/dev/null \
    || { color_red "❌ SHA256 校验失败，已中止以防供应链污染"; exit 1; }
)
color_grn "✓ SHA256 校验通过"

# 5. 目标目录保护
if [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    color_red "❌ 检测到 $INSTALL_DIR 已有 Sebastian 安装"
    color_red "   全新安装请先删除该目录；升级请使用："
    color_red "       cd $INSTALL_DIR && sebastian update"
    exit 1
  else
    color_red "❌ $INSTALL_DIR 非空但不是 Sebastian 安装目录，已中止以防覆盖"
    exit 1
  fi
fi

# 6. 解压
color_ylw "→ 解压到 $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
tar xzf "${TMPDIR}/${TAR_NAME}" -C "$INSTALL_DIR" --strip-components=1

# 7. 运行 install.sh
cd "$INSTALL_DIR"
if [[ ! -x scripts/install.sh ]]; then
  color_red "❌ 解压后未找到 scripts/install.sh"
  exit 1
fi
color_grn "✓ 开始执行安装脚本"
exec ./scripts/install.sh
