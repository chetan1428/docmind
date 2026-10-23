#!/usr/bin/env bash
# Runs ON the EC2 k3s node (via AWS SSM Run Command), from a checkout of the repo.
set -euo pipefail

SHA="${1:?usage: aws-deploy.sh <git-sha>}"
NS=docmind-aws
REGION=ap-south-1
ECR=975739936766.dkr.ecr.ap-south-1.amazonaws.com
AWS=/snap/bin/aws
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

TOKEN=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
IP=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)

kubectl -n "$NS" create secret docker-registry ecr-pull \
  --docker-server="$ECR" --docker-username=AWS \
  --docker-password="$("$AWS" ecr get-login-password --region "$REGION")" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install docmind helm/docmind -n "$NS" \
  -f helm/docmind/values-aws.yaml \
  --set image.tag="$SHA" \
  --set gateway.hostname="$IP.nip.io" \
  --wait --timeout 5m

echo "Deployed $SHA to http://$IP.nip.io"
