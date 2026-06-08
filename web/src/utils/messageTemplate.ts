const PLACEHOLDER = /\{(\w+)\}/g

export function renderMessageTemplate(
  template: string,
  variables: Record<string, string>,
): string {
  return template.replace(PLACEHOLDER, (_, key: string) => {
    if (key in variables) {
      return variables[key]
    }
    return `{${key}}`
  })
}

export function renderStrictTemplatePreview(
  template: string,
  textVariables: Record<string, string>,
  segmentLabels: Record<string, string>,
): string {
  const parts: string[] = []
  let lastIndex = 0

  template.replace(PLACEHOLDER, (match, key: string, offset: number) => {
    if (offset > lastIndex) {
      parts.push(renderMessageTemplate(template.slice(lastIndex, offset), textVariables))
    }
    if (key in segmentLabels) {
      parts.push(segmentLabels[key])
    } else if (key in textVariables) {
      parts.push(textVariables[key])
    } else {
      parts.push(`{${key}}`)
    }
    lastIndex = offset + match.length
    return match
  })

  if (lastIndex < template.length) {
    parts.push(renderMessageTemplate(template.slice(lastIndex), textVariables))
  }

  return parts.join('').trim()
}

export function insertIntoTextarea(
  textarea: HTMLTextAreaElement,
  currentValue: string,
  insertText: string,
): { nextValue: string; cursor: number } {
  const start = textarea.selectionStart ?? currentValue.length
  const end = textarea.selectionEnd ?? currentValue.length
  const nextValue = currentValue.slice(0, start) + insertText + currentValue.slice(end)
  return { nextValue, cursor: start + insertText.length }
}
