#!/bin/bash
set -euo pipefail

# Creates a private repo for a candidate from the template,
# removes the interviewer guide, and adds them as a collaborator.
#
# Usage: ./scripts/create-candidate-repo.sh <candidate-name> [github-username]
#
# Examples:
#   ./scripts/create-candidate-repo.sh jane-doe janedoe
#   ./scripts/create-candidate-repo.sh john-smith              # skip collaborator invite

CANDIDATE_NAME="${1:?Usage: $0 <candidate-name> [github-username]}"
GITHUB_USER="${2:-}"
ORG="rutmehta"
TEMPLATE="${ORG}/arc-agent-interview"
REPO_NAME="arc-interview-${CANDIDATE_NAME}"

echo "Creating ${ORG}/${REPO_NAME} from template..."
gh repo create "${ORG}/${REPO_NAME}" \
  --template "${TEMPLATE}" \
  --private \
  --clone

cd "${REPO_NAME}"

# Remove interviewer-only files
git rm INTERVIEWER_GUIDE.md
git commit -m "Remove interviewer guide for candidate repo"
git push

echo ""
echo "Repo created: https://github.com/${ORG}/${REPO_NAME}"

if [ -n "${GITHUB_USER}" ]; then
  echo "Adding ${GITHUB_USER} as collaborator..."
  gh api "repos/${ORG}/${REPO_NAME}/collaborators/${GITHUB_USER}" \
    -X PUT -f permission=push --silent
  echo "Invite sent to ${GITHUB_USER}"
fi

echo ""
echo "Share with candidate:"
echo "  git clone https://github.com/${ORG}/${REPO_NAME}.git"
