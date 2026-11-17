#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"
curl --fail --silent --show-error "$base_url/health/live"
printf '\n'
curl --fail --silent --show-error "$base_url/health/ready"
printf '\n'
curl --fail --silent --show-error "$base_url/api/summary"
printf '\n'
