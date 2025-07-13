#!/bin/bash
# Safe git operations with lock handling for parallel agents

set -euo pipefail

# Function to wait for git lock to be released
wait_for_git_lock() {
    local max_attempts=30
    local attempt=0
    
    while [ -f .git/index.lock ]; do
        if [ $attempt -ge $max_attempts ]; then
            echo "ERROR: Git lock persisted for too long. Cleaning up..."
            rm -f .git/index.lock
            return 1
        fi
        
        echo "Git lock detected. Waiting... (attempt $((attempt + 1))/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done
    
    return 0
}

# Function to execute git command with retry
git_with_retry() {
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        # Wait for any existing lock
        wait_for_git_lock
        
        # Try to execute the git command
        if "$@"; then
            return 0
        else
            local exit_code=$?
            
            # Check if it's a lock error
            if [[ $exit_code -eq 128 ]] && [[ "$*" == *"git"* ]]; then
                echo "Git operation failed, likely due to lock. Retrying..."
                retry=$((retry + 1))
                sleep 2
            else
                # Not a lock error, fail immediately
                return $exit_code
            fi
        fi
    done
    
    echo "ERROR: Git operation failed after $max_retries retries"
    return 1
}

# Main execution
if [ $# -eq 0 ]; then
    echo "Usage: $0 <git command>"
    echo "Example: $0 git add file.py"
    exit 1
fi

# Execute the command with retry logic
git_with_retry "$@"