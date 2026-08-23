#!/bin/sh
# GitLab Kaniko 作业入口。逻辑放在文件里，避免 CI YAML 被 eval 时把 $( / \( 拆坏。
set -eu

mkdir -p /kaniko/.docker

gitlab_image="${CI_REGISTRY_IMAGE:?}"
dest="--destination ${gitlab_image}:${CI_COMMIT_SHORT_SHA:?}"
if [ -n "${CI_COMMIT_TAG:-}" ]; then
	dest="${dest} --destination ${gitlab_image}:${CI_COMMIT_TAG}"
else
	dest="${dest} --destination ${gitlab_image}:${CI_COMMIT_REF_SLUG:?}"
fi
if [ "${CI_COMMIT_BRANCH:-}" = "${CI_DEFAULT_BRANCH:-}" ]; then
	dest="${dest} --destination ${gitlab_image}:latest"
fi

if [ -n "${HARBOR_USER:-}" ] && [ -n "${HARBOR_PASSWORD:-}" ]; then
	harbor_registry="${HARBOR_REGISTRY:-harbor.cyxc.club}"
	harbor_image="${HARBOR_IMAGE:-${harbor_registry}/cyxc1124/cyxcbot}"
	printf '{"auths":{"%s":{"username":"%s","password":"%s"},"%s":{"username":"%s","password":"%s"}}}\n' \
		"${CI_REGISTRY:?}" "${CI_REGISTRY_USER:?}" "${CI_REGISTRY_PASSWORD:?}" \
		"${harbor_registry}" "${HARBOR_USER}" "${HARBOR_PASSWORD}" \
		>/kaniko/.docker/config.json
	dest="${dest} --destination ${harbor_image}:${CI_COMMIT_SHORT_SHA}"
	if [ -n "${CI_COMMIT_TAG:-}" ]; then
		dest="${dest} --destination ${harbor_image}:${CI_COMMIT_TAG}"
	else
		dest="${dest} --destination ${harbor_image}:${CI_COMMIT_REF_SLUG}"
	fi
	if [ "${CI_COMMIT_BRANCH:-}" = "${CI_DEFAULT_BRANCH:-}" ]; then
		dest="${dest} --destination ${harbor_image}:latest"
	fi
else
	printf '{"auths":{"%s":{"username":"%s","password":"%s"}}}\n' \
		"${CI_REGISTRY:?}" "${CI_REGISTRY_USER:?}" "${CI_REGISTRY_PASSWORD:?}" \
		>/kaniko/.docker/config.json
	echo "HARBOR_USER / HARBOR_PASSWORD unset, skip Harbor"
fi

echo "Destinations:${dest}"

# shellcheck disable=SC2086
exec /kaniko/executor \
	--context "${CI_PROJECT_DIR:?}" \
	--dockerfile "${CI_PROJECT_DIR}/Dockerfile" \
	--build-arg "GIT_TAG=${CI_COMMIT_TAG:-}" \
	--build-arg "GIT_COMMIT=${CI_COMMIT_SHA:?}" \
	--build-arg "GIT_BRANCH=${CI_COMMIT_BRANCH:-}" \
	--build-arg "BUILD_TIME=${CI_JOB_STARTED_AT:-}" \
	--build-arg "BUILD_NUMBER=${CI_PIPELINE_IID:?}" \
	--cache=true \
	--cache-repo="${gitlab_image}/cache" \
	--compressed-caching=false \
	${dest}
