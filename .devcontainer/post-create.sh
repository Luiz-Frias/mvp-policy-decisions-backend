#!/bin/bash

echo "🚀 Starting post-create setup..."

# Ensure we're in the correct directory
cd /home/devuser/workspace

# Update package lists
sudo apt-get update

# Set up Git configuration (user will need to customize)
echo "📝 Setting up Git configuration..."
git config --global init.defaultBranch main
git config --global pull.rebase false
git config --global core.autocrlf input

# Install global npm packages
echo "📦 Installing global npm packages..."
pnpm add -g \
    @commitlint/cli \
    @commitlint/config-conventional \
    husky \
    lint-staged \
    prettier \
    eslint \
    typescript \
    ts-node \
    nodemon \
    pm2

# Set up Python environment
echo "🐍 Setting up Python environment..."
# Activate conda environment
source /opt/conda/etc/profile.d/conda.sh
conda activate base

# Install common Python packages with uv
/home/devuser/.cargo/bin/uv pip install --system \
    black \
    flake8 \
    isort \
    pytest \
    pytest-cov \
    jupyter \
    ipython \
    requests \
    fastapi \
    uvicorn \
    pandas \
    numpy \
    matplotlib \
    seaborn

# Set up Rust environment
echo "🦀 Setting up Rust environment..."
source /home/devuser/.cargo/env
rustup component add clippy rustfmt rust-analyzer

# Install common Rust tools
cargo install \
    cargo-watch \
    cargo-edit \
    cargo-audit \
    serde_json

# Create common development directories
echo "📁 Creating development directories..."
mkdir -p /home/devuser/software_development/templates
mkdir -p /home/devuser/software_development/projects
mkdir -p /home/devuser/software_development/scripts

# Set up SSH directory with proper permissions
mkdir -p /home/devuser/.ssh
chmod 700 /home/devuser/.ssh

# Set up GPG directory
mkdir -p /home/devuser/.gnupg
chmod 700 /home/devuser/.gnupg

# Create a default .gitignore template
cat > /home/devuser/software_development/templates/.gitignore << 'EOF'
# Dependencies
node_modules/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Build outputs
dist/
build/
*.egg-info/
target/

# Environment files
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# Logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# Optional npm cache directory
.npm

# Optional eslint cache
.eslintcache

# Output of 'npm pack'
*.tgz

# Yarn Integrity file
.yarn-integrity

# parcel-bundler cache (https://parceljs.org/)
.cache
.parcel-cache

# next.js build output
.next

# nuxt.js build output
.nuxt

# vuepress build output
.vuepress/dist

# Serverless directories
.serverless

# FuseBox cache
.fusebox/

# DynamoDB Local files
.dynamodb/

# TernJS port file
.tern-port
EOF

# Create development profile
cat > /home/devuser/.bashrc_dev << 'EOF'
# Development environment setup
export PATH="/home/devuser/.cargo/bin:/opt/rust/bin:/opt/conda/bin:$PATH"
export PYTHONPATH="/home/devuser/workspace:$PYTHONPATH"
export NODE_ENV="development"

# Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline'
alias gd='git diff'

# Python aliases
alias py='python'
alias pip='uv pip'

# Node.js aliases
alias ni='pnpm install'
alias nr='pnpm run'
alias ns='pnpm start'
alias nb='pnpm build'
alias nt='pnpm test'

# Rust aliases
alias cr='cargo run'
alias cb='cargo build'
alias ct='cargo test'
alias cc='cargo check'

# Development shortcuts
alias dev='cd /home/devuser/software_development'
alias work='cd /home/devuser/workspace'

# Tool shortcuts
alias snyk-scan='snyk test'
alias security-audit='snyk test && cargo audit'

echo "🛠️  Development environment ready!"
echo "📁 Workspace: /home/devuser/workspace"
echo "💾 Projects: /home/devuser/software_development"
echo ""
echo "🔧 Available tools:"
echo "  • Python 3.11 + uv + conda"
echo "  • Node.js 20.18.1 + pnpm"
echo "  • Rust + cargo"
echo "  • GitHub CLI, Railway CLI, Vercel CLI, Doppler CLI"
echo "  • Snyk, DVC, GNUPG"
echo ""
echo "📝 Quick commands:"
echo "  • 'dev' - Go to development directory"
echo "  • 'work' - Go to workspace"
echo "  • 'security-audit' - Run security scans"
EOF

# Source the development profile
echo "source ~/.bashrc_dev" >> /home/devuser/.bashrc

# Set proper ownership
sudo chown -R devuser:devuser /home/devuser/

echo "✅ Post-create setup completed!"
echo "🎉 Your development environment is ready!"
echo ""
echo "Next steps:"
echo "1. Configure Git: git config --global user.name 'Your Name'"
echo "2. Configure Git: git config --global user.email 'your.email@example.com'"
echo "3. Set up SSH keys for GitHub"
echo "4. Authenticate with CLI tools (gh auth login, etc.)"
