import { type FormEvent, useState } from 'react'
import { useLogin } from '../api/hooks'

export function LoginView() {
  const [password, setPassword] = useState('')
  const login = useLogin()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (password) login.mutate(password)
  }

  return (
    <div className="m-auto w-80">
      <form onSubmit={submit} className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-6">
        <h1 className="m-0 text-xl font-bold text-accent">חילוץ טפסי התחייבות</h1>
        <label className="flex flex-col gap-1 text-sm text-sub">
          סיסמה
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus autoComplete="current-password"
            className="rounded-lg border border-line bg-surface px-3 py-2 text-base text-ink" />
        </label>
        {login.error && <div role="alert" className="text-sm text-warn-ink">{login.error.message}</div>}
        <button type="submit" disabled={!password || login.isPending}
          className="rounded-lg border-0 bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          כניסה
        </button>
      </form>
    </div>
  )
}
