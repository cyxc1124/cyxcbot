{{/*
Expand the name of the chart.
*/}}
{{- define "cyxcbot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "cyxcbot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "cyxcbot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "cyxcbot.labels" -}}
helm.sh/chart: {{ include "cyxcbot.chart" . }}
{{ include "cyxcbot.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "cyxcbot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cyxcbot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
容器镜像 tag：values.image.tag 优先，留空则 v + Chart.appVersion（匹配 GHCR 发布格式）
*/}}
{{- define "cyxcbot.imageTag" -}}
{{- $tag := .Values.image.tag | default (printf "v%s" .Chart.AppVersion) -}}
{{- $tag -}}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "cyxcbot.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "cyxcbot.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
WEB_SECRET_KEY 所用 Secret 名称：
  - secret.name 有值 → 引用用户自建的 Secret（方式 A）
  - secret.name 为空且 secret.value 有值 → <release>-secret（方式 B，由 templates/secret.yaml 创建）
*/}}
{{- define "cyxcbot.secretName" -}}
{{- if .Values.secret.name -}}
{{- .Values.secret.name -}}
{{- else if .Values.secret.value -}}
{{- printf "%s-secret" (include "cyxcbot.fullname" .) -}}
{{- else -}}
{{- fail "secret.name 或 secret.value 必须设置其一，详见 deploy/helm/README.md" -}}
{{- end -}}
{{- end -}}

{{/*
SQLite 数据卷 PVC 名称：
  - persistence.existingClaim 有值 → 复用已有 PVC
  - 否则 → <release>-data（由 templates/pvc.yaml 创建）
*/}}
{{- define "cyxcbot.dataClaimName" -}}
{{- if .Values.persistence.existingClaim -}}
{{- .Values.persistence.existingClaim -}}
{{- else -}}
{{- printf "%s-data" (include "cyxcbot.fullname" .) -}}
{{- end -}}
{{- end -}} 