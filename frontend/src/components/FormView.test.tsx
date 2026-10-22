import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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


describe('FormView: keyboard shortcuts', () => {
  const list = () => screen.getByLabelText('רשימת הטפסים', { selector: 'aside' })

  it('shows the shortcuts on screen', async () => {
    await open()
    const hint = screen.getByLabelText('קיצורי מקלדת')
    for (const key of ['↑', '↓', 'N', 'A', 'L']) expect(hint).toHaveTextContent(key)
  })

  it('the arrow keys move to the next and previous form, going round at the ends', async () => {
    const { user } = await open('a')
    await user.keyboard('{ArrowDown}')
    expect(title()).toHaveTextContent('רונן לוי')
    await user.keyboard('{ArrowDown}{ArrowDown}')
    expect(title()).toHaveTextContent('דנה כהן')             // wrapped round
    await user.keyboard('{ArrowUp}')
    expect(title()).toHaveTextContent('משה ישראלי')
  })

  it('N jumps to the next form that needs review, skipping clean ones', async () => {
    const { user } = await open('a')
    await user.keyboard('n')
    expect(title()).toHaveTextContent('רונן לוי')
    await user.keyboard('n')
    expect(title()).toHaveTextContent('משה ישראלי')
  })

  it('works on a Hebrew keyboard: it is the physical key that counts', async () => {
    await open('a')
    fireEvent.keyDown(window, { code: 'KeyN', key: 'ט' })
    expect(title()).toHaveTextContent('רונן לוי')
  })

  it('L opens and closes the list of forms', async () => {
    const { user } = await open()
    expect(list()).toHaveStyle({ width: '236px' })
    await user.keyboard('l')
    expect(list()).toHaveStyle({ width: '0px' })
    await user.keyboard('l')
    expect(list()).toHaveStyle({ width: '236px' })
  })

  describe('A approves, but only a form with nothing left to check', () => {
    it('refuses a form that still has flagged fields, and says why', async () => {
      const { api, user } = await open('b')
      await user.keyboard('a')
      expect(await screen.findByRole('status')).toHaveTextContent('אי אפשר לאשר במקלדת כשיש שדות לבדיקה')
      expect(api.called('POST', '/approve')).toHaveLength(0)
      expect(api.records.find((r) => r.id === 'b')?.status).toBe('pending')
    })

    it('the refusal does not follow you to another form', async () => {
      const { user } = await open('b')
      await user.keyboard('a')
      await screen.findByRole('status')
      await user.keyboard('{ArrowDown}')
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('approves a clean form and moves on to the next one that needs review', async () => {
      const { api, user } = await open('a')
      await user.keyboard('a')
      await waitFor(() => expect(api.called('POST', '/records/a/approve')).toHaveLength(1))
      await waitFor(() => expect(title()).toHaveTextContent('רונן לוי'))
    })

    it('does nothing on a form that is already approved', async () => {
      const { api, user } = await open('a', [makeRecord('a', { status: 'approved' }), flaggedRecord('b', 'רונן', 'לוי')])
      await user.keyboard('a')
      expect(api.called('POST', '/approve')).toHaveLength(0)
    })

    it('the button still lets a person deliberately approve a flagged form', async () => {
      const { api, user } = await open('b')
      await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
      await waitFor(() => expect(api.called('POST', '/records/b/approve')).toHaveLength(1))
    })
  })

  describe('never gets in the way of typing or of browser commands', () => {
    it('typing in a field editor does not trigger a shortcut', async () => {
      const { api, user } = await open('b')
      await user.click(screen.getByText('939376'))
      const box = screen.getByLabelText('מספר מרכזי')
      await user.type(box, 'nal')                       // N, A and L are all shortcuts
      expect(box).toHaveValue('939376nal')
      expect(title()).toHaveTextContent('רונן לוי')
      expect(api.called('POST', '/approve')).toHaveLength(0)
      expect(list()).toHaveStyle({ width: '236px' })
    })

    it('typing in the search box does not trigger a shortcut', async () => {
      const { user } = await open('a')
      await user.type(screen.getByLabelText('חיפוש טפסים'), 'nal')
      expect(title()).toHaveTextContent('דנה כהן')
    })

    it('Ctrl+A stays "select all" and does not approve', async () => {
      const { api, user } = await open('a')
      await user.keyboard('{Control>}a{/Control}')
      expect(api.called('POST', '/approve')).toHaveLength(0)
    })

    it('the shortcuts are off while the full-screen viewer is open', async () => {
      const { api, user } = await open('a')
      await user.click(screen.getByRole('button', { name: 'הרחבה למסך מלא' }))
      await user.keyboard('a')
      expect(api.called('POST', '/approve')).toHaveLength(0)
      await user.keyboard('{Escape}')
      await user.keyboard('a')                          // closed again: now it works
      await waitFor(() => expect(api.called('POST', '/records/a/approve')).toHaveLength(1))
    })
  })
})

describe('FormView: forms that are uploaded but not read yet', () => {
  const waiting = (over = {}) => ({
    id: 'p1', document_id: 'd1', filename: 'scan.pdf', page_number: 1, status: 'processing' as const, error: null, ...over,
  })

  function WithPending({ pending, records, start }: { pending: ReturnType<typeof waiting>[]; records: ReturnType<typeof forms>; start: string | null }) {
    const [selected, setSelected] = useState<string | null>(start)
    return <div className="flex h-96"><FormView records={records} pending={pending} selectedId={selected} onSelect={setSelected} /></div>
  }

  it('shows the form image at once, with the fields still empty and a note that they are being read', () => {
    installFakeApi([])
    renderWithClient(<WithPending pending={[waiting()]} records={[]} start="p1" />)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('scan.pdf · עמוד 1')
    expect(screen.getByRole('status')).toHaveTextContent('קורא את השדות')
    expect(document.querySelector('img[src="/api/pages/p1/image"]')).toBeInTheDocument()
  })

  it('lists it among the other forms and lets the user move to it and back', async () => {
    installFakeApi(forms())
    renderWithClient(<WithPending pending={[waiting()]} records={forms()} start="a" />)
    await screen.findByRole('heading', { name: /דנה כהן/ })
    await userEvent.setup().click(screen.getByRole('button', { name: /scan\.pdf · עמוד 1/ }))
    expect(screen.getByRole('status')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: /דנה כהן/ }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('opens the finished record where the page was selected', async () => {
    installFakeApi(forms())
    const records = [{ ...makeRecord('r9'), page_ids: ['p1'] }]
    renderWithClient(<WithPending pending={[]} records={records} start="p1" />)
    expect(await screen.findByRole('heading', { name: /דנה כהן/ })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('offers a retry when reading failed', async () => {
    const api = installFakeApi([])
    renderWithClient(<WithPending pending={[waiting({ status: 'error', error: 'RateLimited' })]} records={[]} start="p1" />)
    expect(screen.getByRole('alert')).toHaveTextContent('RateLimited')
    await userEvent.setup().click(screen.getByRole('button', { name: 'נסי שוב' }))
    await waitFor(() => expect(api.called('POST', '/pages/p1/reprocess')).toHaveLength(1))
  })
})
