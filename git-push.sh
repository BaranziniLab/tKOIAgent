#!/bin/bash
# Git commit and push automation script
# Usage: ./git-push.sh "your commit message"
# If no message provided, defaults to "automatic commit"

# Set default commit message or use provided one
COMMIT_MESSAGE="${1:-automatic commit}"

# Add all changes
echo "Staging changes..."
git add .

# Commit with message and co-author
echo "Committing changes..."
git commit -m "${COMMIT_MESSAGE}"

# Push to main branch
echo "Pushing to main..."
git push origin main

echo "Done!"

