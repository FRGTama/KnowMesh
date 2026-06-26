export async function uploadFile(file, strategy) {
  const form = new FormData()
  form.append('file', file)
  form.append('strategy', strategy)
  const res = await fetch('/upload', { method: 'POST', body: form })
  return res.json()
}

export async function query(text, provider, model) {
  const form = new FormData()
  form.append('query', text)
  form.append('provider', provider)
  form.append('model', model)
  const res = await fetch('/query', { method: 'POST', body: form })
  return res.json()
}

export async function getCollectionInfo() {
  const res = await fetch('/collection-info')
  return res.json()
}

export async function clearDatabase() {
  const res = await fetch('/clear', { method: 'POST' })
  return res.json()
}
