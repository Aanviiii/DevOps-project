{{/* Base name for every object: the release name, e.g. "shelfwise". */}}
{{- define "shelfwise.fullname" -}}
{{- .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}

{{/* Labels shared by every object, minus the ones the selector labels provide. */}}
{{- define "shelfwise.baseLabels" -}}
app.kubernetes.io/part-of: shelfwise
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | default .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Labels for objects that do not belong to one component (Secret, Ingress, ...). */}}
{{- define "shelfwise.labels" -}}
{{ include "shelfwise.baseLabels" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Selector labels for one component. Usage: include "shelfwise.selector" (list . "backend") */}}
{{- define "shelfwise.selector" -}}
{{- $ctx := index . 0 -}}
app.kubernetes.io/name: {{ index . 1 }}
app.kubernetes.io/instance: {{ $ctx.Release.Name }}
{{- end -}}

{{/* Full image reference for a Shelfwise component. */}}
{{- define "shelfwise.image" -}}
{{- $ctx := index . 0 -}}
{{- $tag := required "image.tag is required (sha-<commit> pushed by CI)" $ctx.Values.image.tag -}}
{{- printf "%s/shelfwise-%s:%s" $ctx.Values.image.registry (index . 1) $tag -}}
{{- end -}}

{{/* Name of the Secret holding database credentials. */}}
{{- define "shelfwise.dbSecret" -}}
{{- .Values.postgres.existingSecret | default (printf "%s-db" (include "shelfwise.fullname" .)) -}}
{{- end -}}

{{- define "shelfwise.postgresHost" -}}
{{- printf "%s-postgres" (include "shelfwise.fullname" .) -}}
{{- end -}}

{{- define "shelfwise.backendService" -}}
{{- printf "%s-backend" (include "shelfwise.fullname" .) -}}
{{- end -}}

{{- define "shelfwise.frontendService" -}}
{{- printf "%s-frontend" (include "shelfwise.fullname" .) -}}
{{- end -}}
