#!/bin/bash
# Runs once, as root, on the first boot (cloud-init). Log: /var/log/docmind-bootstrap.log
set -euxo pipefail
exec > /var/log/docmind-bootstrap.log 2>&1
export HOME=/root

# Kubernetes (k3s) without its built-in Traefik; we use Envoy Gateway
curl -sfL https://get.k3s.io | sh -s - --disable traefik --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Tools the deploy script needs
snap install aws-cli --classic
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Wait for the node
until kubectl get nodes 2>/dev/null | grep -q " Ready"; do sleep 5; done

# Gateway API controller + GatewayClass
helm install eg oci://docker.io/envoyproxy/gateway-helm --version v1.9.2 \
  -n envoy-gateway-system --create-namespace --wait --timeout 10m
kubectl apply -f - <<'EOF'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: eg
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
EOF

kubectl create namespace docmind-aws
echo "BOOTSTRAP_DONE"
