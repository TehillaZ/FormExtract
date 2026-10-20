import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { useRecords } from '../api/hooks'
import { flaggedRecord, makeRecord } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { FormView } from './FormView'

/** The page owns which form is selected; this stands in for it. */
function Screen({ start = null }: { start?: string | null }) {
  const { data = [] } = useRecords()
  const [selected, setSelected] = useState<string | null>(start)
  return <div className="flex h-96"><FormView records={data} selectedId={selected} onSelect={setSelected} /></div>
}

const forms = () => [
  makeRecord('a'),                                   // דנה כהן, clean
  flaggedRecord('b', 'רונן', 'לוי'),
  flaggedRecord('c', 'משה', 'ישראלי'),
]

const title = () => screen.getByRole('heading', { level: 2 })

async function open(start: string | null = 'a', records = forms()) {
  const api = installFakeApi(records)
  renderWithClient(<Screen start={start} />)
  await screen.findByRole('heading', { level: 2 })
  return { api, user: userEvent.setup() }
}

describe('FormView: the form list can be closed and opened', () => {
  it('closing the list gives its space back and offers a button to open it again', async () => {
    const { user } = await open()
    const list = () => screen.getByLabelText('רשימת הטפסים', { selector: 'aside' })
    expect(list()).toHaveStyle({ width: '236px' })

    await user.click(screen.getByRole('button', { name: 'סגירת הרשימה' }))
    expect(list()).toHaveStyle({ width: '0px' })
    const reopen = screen.getByRole('button', { name: 'פתיחת רשימת הטפסים' })
    expect(reopen).toHaveTextContent('טפסים (3)')

    await user.click(reopen)
    expect(list()).toHaveStyle({ width: '236px' })
    expect(screen.queryByRole('button', { name: 'פתיחת רשימת הטפסים' })).not.toBeInTheDocument()
  })

  it('remembers the choice the next time the screen is shown', async () => {
    const { user } = await open()
    await user.click(screen.getByRole('button', { name: 'סגירת הרשימה' }))
    expect(localStorage.getItem('formlist-open')).toBe('0')

    document.body.innerHTML = ''
    installFakeApi(forms())
    renderWithClient(<Screen start="a" />)
    expect(await screen.findByRole('button', { name: 'פתיחת רשימת הטפסים' })).toBeInTheDocument()
  })

  it('still works with the list closed: the open form can be approved', async () => {
    const { api, user } = await open()
    await user.click(screen.getByRole('button', { name: 'סגירת הרשימה' }))
    await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
    await waitFor(() => expect(api.called('POST', '/records/a/approve')).toHaveLength(1))
  })
})

describe('FormView: moving between forms', () => {
  it('shows the form picked in the list', async () => {
    const { user } = await open('a')
    expect(title()).toHaveTextContent('דנה כהן')
    await user.click(screen.getByRole('button', { name: /משה ישראלי/ }))
    expect(title()).toHaveTextContent('משה ישראלי')
  })

  it('falls back to the first form when nothing is selected', async () => {
    await open(null)
    expect(title()).toHaveTextContent('דנה כהן')
  })

  it('"next to review" jumps to the next form with something flagged, skipping clean ones', async () => {
    const { user } = await open('a')
    await user.click(screen.getByRole('button', { name: 'הבא לבדיקה' }))
    expect(title()).toHaveTextContent('רונן לוי')
    await user.click(screen.getByRole('button', { name: 'הבא לבדיקה' }))
    expect(title()).toHaveTextContent('משה ישראלי')
    await user.click(screen.getByRole('button', { name: 'הבא לבדיקה' }))   // wraps around
    expect(title()).toHaveTextContent('רונן לוי')
  })

  it('"next to review" is disabled when no other form needs review', async () => {
    await open('a', [makeRecord('a'), makeRecord('b', { first_name: { ...makeRecord('x').first_name, value: 'אבי' } })])
    expect(screen.getByRole('button', { name: 'הבא לבדיקה' })).toBeDisabled()
  })

  it('approving a form moves on to the next one that needs review', async () => {
    const { api, user } = await open('b')
    await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
    await waitFor(() => expect(title()).toHaveTextContent('משה ישראלי'))
    expect(api.records.find((r) => r.id === 'b')?.status).toBe('approved')
  })

  it('stays on the form and explains when approving is refused', async () => {
    const { api, user } = await open('b')
    api.approveError = 'מספר התחייבות כבר קיים ברשומה מאושרת: 730578626'
    await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('כבר קיים ברשומה מאושרת')
    expect(title()).toHaveTextContent('רונן לוי')
  })

  it('the refusal message does not follow you to another form', async () => {
    const { api, user } = await open('b')
    api.approveError = 'כפול'
    await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: /דנה כהן/ }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('FormView: the form image', () => {
  it('shows the page image of the open form, from the API', async () => {
    await open('b')
    expect(screen.getByAltText('תמונת הטופס')).toHaveAttribute('src', '/api/pages/page-b/image')
  })

  it('shows a helpful message when the form has no image', async () => {
    await open('a', [makeRecord('a', { page_ids: [] })])
    expect(screen.getByText('אין תמונה לטופס')).toBeInTheDocument()
  })

  it('says so when there are no forms at all', async () => {
    installFakeApi([])
    renderWithClient(<Screen />)
    expect(await screen.findByText(/אין טפסים עדיין/)).toBeInTheDocument()
  })
})

describe('FormView: expanded view', () => {
  it('opens full screen and closes with Escape', async () => {
    const { user } = await open('b')
    await user.click(screen.getByRole('button', { name: 'הרחבה למסך מלא' }))
    const dialog = screen.getByRole('dialog', { name: 'תצוגה מוגדלת של הטופס' })
    expect(within(dialog).getByText('רונן לוי')).toBeInTheDocument()
    expect(within(dialog).getByText('טופס 2 מתוך 3')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('steps to the next and previous forms from inside the viewer', async () => {
    const { user } = await open('a')
    await user.click(screen.getByRole('button', { name: 'הרחבה למסך מלא' }))
    const dialog = screen.getByRole('dialog')

    await user.click(within(dialog).getByRole('button', { name: 'הטופס הבא' }))
    expect(within(dialog).getByText('רונן לוי')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'הטופס הקודם' }))
    expect(within(dialog).getByText('דנה כהן')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'הטופס הקודם' }))   // wraps to the last
    expect(within(dialog).getByText('משה ישראלי')).toBeInTheDocument()
  })
})
