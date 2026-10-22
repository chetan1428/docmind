{{- define "docmind.labels" -}}
app.kubernetes.io/name: docmind
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "docmind.image" -}}
{{ .Values.image.repository }}:{{ required "image.tag is required: pass --set image.tag=<git sha>" .Values.image.tag }}
{{- end }}
