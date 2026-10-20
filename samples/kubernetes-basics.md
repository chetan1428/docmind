# Kubernetes Basics

A Pod is the smallest deployable unit in Kubernetes. A pod wraps one or more containers that share the same network namespace and storage volumes.

A Deployment manages a set of identical pods. It keeps the desired number of replicas running and performs rolling updates when you change the container image. If a pod crashes, the Deployment's ReplicaSet creates a new one.

A Service gives a stable network name and IP to a group of pods selected by labels. ClusterIP services are reachable only inside the cluster, NodePort exposes a port on every node, and LoadBalancer asks the cloud provider for an external load balancer.

An Ingress routes external HTTP traffic to services based on host names and paths. It needs an ingress controller such as ingress-nginx or the AWS Load Balancer Controller.

A liveness probe tells Kubernetes whether a container is still alive. If the liveness probe fails, the kubelet restarts the container. A readiness probe tells Kubernetes whether a pod can receive traffic. If the readiness probe fails, the pod is removed from the Service endpoints but is not restarted.

ConfigMaps store non-secret configuration such as feature flags and URLs. Secrets store sensitive values such as passwords and API keys. Both can be injected into pods as environment variables or mounted files.

A Horizontal Pod Autoscaler (HPA) scales the number of pod replicas based on CPU, memory or custom metrics. The metrics-server must be installed for CPU-based autoscaling, and pods must declare resource requests.

A StatefulSet is used for stateful workloads such as databases. Each pod gets a stable name and its own PersistentVolumeClaim, so data survives pod restarts.

# Docker Basics

A Dockerfile describes how to build an image. Multi-stage builds use one stage to install build tools and dependencies and a smaller final stage that only contains what is needed at runtime, which reduces image size and attack surface.

Containers should run as a non-root user. Use a .dockerignore file so that secrets, git history and local virtual environments are not copied into the image.

# CI/CD Basics

Continuous Integration runs linting and tests on every pull request. Continuous Delivery builds a versioned artifact, such as a container image tagged with the git commit SHA, and deploys it automatically. GitOps tools such as ArgoCD watch a git repository and keep the cluster in sync with the manifests stored there.
