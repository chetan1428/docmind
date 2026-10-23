#!/usr/bin/env bash
# Runs ON the EC2 k3s node (via AWS SSM Run Command), from a checkout of the repo.
set -euo pipefail

SHA="${1:?usage: aws-deploy.sh <git-sha>}"
NS=docmind-aws
REGION=ap-south-1
ECR=975739936766.dkr.ecr.ap-south-1.amazonaws.com
AWS=/snap/bin/aws
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

param() { "$AWS" ssm get-parameter --region "$REGION" --name "$1" --with-decryption --query Parameter.Value --output text; }

TOKEN=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
IP=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)

kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

# Registry login (12h token) using the node's IAM role
kubectl -n "$NS" create secret docker-registry ecr-pull \
  --docker-server="$ECR" --docker-username=AWS \
  --docker-password="$("$AWS" ecr get-login-password --region "$REGION")" \
  --dry-run=client -o yaml | kubectl apply -f -

# App secrets from Parameter Store (never stored in git or typed by hand)
SECRET_RESULT=$(kubectl -n "$NS" create secret generic docmind-secrets \
  --from-literal=DATABASE_URL="$(param /docmind/DATABASE_URL)" \
  --from-literal=GROQ_API_KEY="$(param /docmind/GROQ_API_KEY)" \
  --dry-run=client -o yaml | kubectl apply -f -)
echo "$SECRET_RESULT"

helm upgrade --install docmind helm/docmind -n "$NS" \
  -f helm/docmind/values-aws.yaml \
  --set image.tag="$SHA" \
  --set gateway.hostname="$IP.nip.io" \
  --wait --timeout 5m

# Pods only read env vars at start: restart them if a secret value changed
if echo "$SECRET_RESULT" | grep -q configured; then
  kubectl -n "$NS" rollout restart deploy/api deploy/worker
  kubectl -n "$NS" rollout status deploy/api --timeout=180s
fi

echo "Deployed $SHA to http://$IP.nip.io"
