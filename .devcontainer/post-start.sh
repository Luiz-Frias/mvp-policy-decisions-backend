#!/bin/bash

echo "🔄 Running post-start checks..."

# Health check for all tools
echo "🔍 Checking tool availability..."

# Check Python and uv
if command -v python &> /dev/null && command -v uv &> /dev/null; then
    echo "✅ Python $(python --version | cut -d' ' -f2) + uv ready"
else
    echo "❌ Python/uv not available"
fi

# Check Node.js and pnpm
if command -v node &> /dev/null && command -v pnpm &> /dev/null; then
    echo "✅ Node.js $(node --version) + pnpm ready"
else
    echo "❌ Node.js/pnpm not available"
fi

# Check Rust
if command -v rustc &> /dev/null && command -v cargo &> /dev/null; then
    echo "✅ Rust $(rustc --version | cut -d' ' -f2) ready"
else
    echo "❌ Rust not available"
fi

# Check CLI tools
tools=("gh" "railway" "vercel" "doppler" "snyk" "dvc")
for tool in "${tools[@]}"; do
    if command -v $tool &> /dev/null; then
        echo "✅ $tool ready"
    else
        echo "❌ $tool not available"
    fi
done

# Check Git configuration
if git config --global user.name &> /dev/null && git config --global user.email &> /dev/null; then
    echo "✅ Git configured for $(git config --global user.name)"
else
    echo "⚠️  Git not configured - run: git config --global user.name 'Your Name'"
    echo "⚠️  Git not configured - run: git config --global user.email 'your.email@example.com'"
fi

# Display current working directory and mounted volumes
echo ""
echo "📍 Current location: $(pwd)"
echo "💾 Mounted volumes:"
if [ -d "/home/devuser/software_development" ]; then
    echo "  ✅ /home/devuser/software_development ($(ls -la /home/devuser/software_development | wc -l) items)"
else
    echo "  ❌ /home/devuser/software_development not mounted"
fi

# Check for existing projects
if [ -d "/home/devuser/software_development/projects" ]; then
    project_count=$(find /home/devuser/software_development/projects -maxdepth 1 -type d | wc -l)
    if [ $project_count -gt 1 ]; then
        echo "📂 Found $((project_count-1)) projects in software_development/projects"
    fi
fi

echo ""
echo "🚀 Container ready for development!"
echo "💡 Use 'dev' to go to /home/devuser/software_development"
echo "💡 Use 'work' to go to /home/devuser/workspace"
