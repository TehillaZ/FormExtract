import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { useRecords } from '../api/hooks'
import { field, flaggedRecord, makeRecord } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { FieldsPanel } from './FieldsPanel'

/** Shows the panel for a record read from the query cache, the way the real screen does:
 *  after a save the cache changes and the panel must follow. */
function Harness({ id, onApprove = () => {}, approveError = null }: { id: string; onApprove?: () => void; approveError?: string | null }) {
  const { data } = useRecords()
  const record = data?.find((r) => r.id === id)
  return record ? (
    <FieldsPanel record={record} onApprove={onApprove} approving={false} approveError={approveError}
      onNextToReview={() => {}} hasNextToReview />
  ) : null
}

const rowOf = (label: string) => screen.getByText(label, { selector: 'div' }).parentElement as HTMLElement
const isFlagged = (label: string) => rowOf(label).dataset.flagged === 'true'

async function open(record = flaggedRecord('a', 'רונן')) {
  const api = installFakeApi([record])
  renderWithClient(<Harness id={record.id} />)
  await screen.findByText('רונן')
  return { api, user: userEvent.setup() }
}

describe('FieldsPanel: what is flagged', () => {
  it('flags the fields that are not verified and counts them in the header', async () => {
    await open(flaggedRecord('a', 'רונן', 'לוי', { sender: field(null, 'low', ['לא נמצא']) }))
    expect(isFlagged('שם פרטי')).toBe(true)
    expect(isFlagged('גורם שולח')).toBe(true)
    expect(isFlagged('ת"ז')).toBe(false)
    expect(screen.getByText('2 לבדיקה')).toBeInTheDocument()
  })

  it('says "not found" for an empty field and shows what was read when the value was rejected', async () => {
    await open(makeRecord('a', {
      first_name: field('רונן', 'low'),
      id_number: field(null, 'low', ['אורך ת"ז לא תקין'], '0011223344'),
    }))
    expect(within(rowOf('ת"ז')).getByText('— לא נמצא')).toBeInTheDocument()
    expect(within(rowOf('ת"ז')).getByText('נקרא: 0011223344')).toBeInTheDocument()
  })
})

describe('FieldsPanel: saving clears the orange', () => {
  it('a corrected value is saved and its flag disappears', async () => {
    const { api, user } = await open()
    await user.click(screen.getByText('רונן'))
    const input = screen.getByLabelText('שם פרטי')
    await user.clear(input)
    await user.type(input, 'דני{Enter}')

    await waitFor(() => expect(isFlagged('שם פרטי')).toBe(false))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ first_name: 'דני' })
    expect(within(rowOf('שם פרטי')).getByText('דני')).toBeInTheDocument()
    expect(within(rowOf('שם פרטי')).getByText('תוקן ידנית')).toBeInTheDocument()
  })

  it('saving the SAME value counts as confirming it: the flag goes away', async () => {
    // the bug reported from real use: re-saving a correct but flagged value left it orange
    const { api, user } = await open()
    await user.click(screen.getByText('רונן'))
    await user.click(screen.getByRole('button', { name: 'שמרי' }))

    await waitFor(() => expect(isFlagged('שם פרטי')).toBe(false))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ first_name: 'רונן' })
    expect(within(rowOf('שם פרטי')).getByText('אושר ידנית')).toBeInTheDocument()
  })

  it('the check button confirms the current value without opening the editor', async () => {
    const { api, user } = await open()
    await user.click(screen.getByRole('button', { name: 'אשרי שהערך של שם פרטי נכון' }))

    await waitFor(() => expect(isFlagged('שם פרטי')).toBe(false))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ first_name: 'רונן' })
    expect(screen.queryByLabelText('שם פרטי')).not.toBeInTheDocument()
  })

  it('an empty field can be confirmed as really empty', async () => {
    const { api, user } = await open(flaggedRecord('a', 'רונן', 'לוי', { commitment_numbers: [field(null, 'low', ['לא נמצא'])] }))
    await user.click(screen.getByRole('button', { name: 'אשרי שמספר התחייבות ריק בטופס' }))

    await waitFor(() => expect(isFlagged('מספר התחייבות')).toBe(false))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ commitment_numbers: [] })
    expect(within(rowOf('מספר התחייבות')).getByText('אושר ידנית: אין בטופס')).toBeInTheDocument()
  })

  it('verified fields have no check button', async () => {
    await open()
    expect(screen.queryByRole('button', { name: 'אשרי שהערך של ת"ז נכון' })).not.toBeInTheDocument()
  })

  it('the header follows: when every flag is cleared it says the form is fine', async () => {
    const { user } = await open()
    expect(screen.getByText('1 לבדיקה')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'אשרי שהערך של שם פרטי נכון' }))
    expect(await screen.findByText('תקין')).toBeInTheDocument()
  })
})

describe('FieldsPanel: editing', () => {
  it('Escape cancels without saving', async () => {
    const { api, user } = await open()
    await user.click(screen.getByText('רונן'))
    await user.type(screen.getByLabelText('שם פרטי'), 'xyz{Escape}')
    expect(screen.queryByLabelText('שם פרטי')).not.toBeInTheDocument()
    expect(api.called('PATCH', '/records')).toHaveLength(0)
    expect(isFlagged('שם פרטי')).toBe(true)
  })

  it('list fields can get another number', async () => {
    const { api, user } = await open(flaggedRecord('a', 'רונן'))
    await user.click(screen.getByText('939376'))
    await user.click(screen.getByRole('button', { name: '+ הוספת מספר' }))
    const boxes = screen.getAllByLabelText('מספר מרכזי')
    await user.type(boxes[1], '939999{Enter}')

    await waitFor(() => expect(api.called('PATCH', '/records/a')).toHaveLength(1))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ central_numbers: ['939376', '939999'] })
    expect(await screen.findByText('939376 · 939999')).toBeInTheDocument()
  })

  it('list fields can lose a number', async () => {
    const { api, user } = await open(flaggedRecord('a', 'רונן', 'לוי', { central_numbers: [field('939376'), field('939377')] }))
    await user.click(screen.getByText('939376 · 939377'))
    await user.click(screen.getAllByRole('button', { name: 'הסרה' })[1])
    await user.click(screen.getByRole('button', { name: 'שמרי' }))

    await waitFor(() => expect(api.called('PATCH', '/records/a')).toHaveLength(1))
    expect(api.called('PATCH', '/records/a')[0].body).toEqual({ central_numbers: ['939376'] })
  })

  it('shows the server message when a value is rejected and stays in the editor', async () => {
    const { api, user } = await open()
    api.patchError = 'מספר מרכזי חייב להכיל 6 ספרות'
    await user.click(screen.getByText('939376'))
    await user.type(screen.getByLabelText('מספר מרכזי'), '1{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('מספר מרכזי חייב להכיל 6 ספרות')
    expect(screen.getByLabelText('מספר מרכזי')).toBeInTheDocument()
  })

  it('shows a failure on the check button without losing the row', async () => {
    const { api, user } = await open()
    api.patchError = 'השרת סירב'
    await user.click(screen.getByRole('button', { name: 'אשרי שהערך של שם פרטי נכון' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('השרת סירב')
    expect(isFlagged('שם פרטי')).toBe(true)
  })
})

describe('FieldsPanel: approving', () => {
  it('calls approve when the button is pressed', async () => {
    const onApprove = vi.fn()
    installFakeApi([makeRecord('a')])
    const user = userEvent.setup()
    renderWithClient(<Harness id="a" onApprove={onApprove} />)
    await screen.findByText('תקין')
    await user.click(screen.getByRole('button', { name: 'אשרי ושמרי' }))
    expect(onApprove).toHaveBeenCalledTimes(1)
  })

  it('shows the error the page passes in, such as a commitment number that is already approved', async () => {
    installFakeApi([makeRecord('a')])
    renderWithClient(<Harness id="a" approveError="מספר התחייבות כבר קיים ברשומה מאושרת: 730578626" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('כבר קיים ברשומה מאושרת: 730578626')
  })

  it('an approved record shows its status and cannot be approved again', async () => {
    installFakeApi([makeRecord('a', { status: 'approved' })])
    renderWithClient(<Harness id="a" />)
    expect(await screen.findByText('מאושר', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'מאושר' })).toBeDisabled()
  })

  it('shows duplicate-number warnings', async () => {
    installFakeApi([makeRecord('a', { duplicate_warnings: ['מספר מרכזי 939376 כבר קיים ברשומה אחרת'] })])
    renderWithClient(<Harness id="a" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('כבר קיים ברשומה אחרת')
  })

  describe('suggestions from earlier corrections', () => {
    const suggestion = {
      field: 'central_numbers', current: '939376', suggested: '939999', times: 3, total: 3, sender: 'כללית',
      examples: [{ old: '939376', new: '939999', at: '2026-10-20T10:00:00Z' }],
    }
    const withSuggestion = () => makeRecord('a', { suggestions: [suggestion] })

    it('offers the earlier fix with how many corrections stand behind it, and does not apply it', async () => {
      const api = installFakeApi([withSuggestion()])
      renderWithClient(<Harness id="a" />)
      const box = await screen.findByRole('group', { name: 'הצעה למספר מרכזי' })
      expect(box).toHaveTextContent('בטפסים קודמים מכללית תוקן 939376 ל-939999')
      expect(box).toHaveTextContent('3 מתוך 3 תיקונים קודמים')
      expect(api.called('PATCH', '/records/a')).toHaveLength(0)
    })

    it('words a sender suggestion as a different reading, not as "from" the very sender in question', async () => {
      installFakeApi([makeRecord('a', { suggestions: [{ ...suggestion, field: 'sender', current: 'שיבא', suggested: 'מאוחדת', sender: 'שיבא' }] })])
      renderWithClient(<Harness id="a" />)
      expect(await screen.findByRole('group', { name: 'הצעה לגורם שולח' })).toHaveTextContent('בטפסים קודמים נקרא הגורם שיבא ותוקן ל-מאוחדת')
    })

    it('applies it only when the user says so', async () => {
      const api = installFakeApi([withSuggestion()])
      renderWithClient(<Harness id="a" />)
      await screen.findByRole('group', { name: 'הצעה למספר מרכזי' })
      await userEvent.setup().click(screen.getByRole('button', { name: 'החילי את ההצעה' }))
      await waitFor(() => expect(api.called('PATCH', '/records/a')).toHaveLength(1))
      expect(api.called('PATCH', '/records/a')[0].body).toEqual({ central_numbers: ['939999'] })
    })

    it('can be ignored', async () => {
      const api = installFakeApi([withSuggestion()])
      renderWithClient(<Harness id="a" />)
      await screen.findByRole('group', { name: 'הצעה למספר מרכזי' })
      await userEvent.setup().click(screen.getByRole('button', { name: 'התעלמי' }))
      expect(screen.queryByRole('group', { name: 'הצעה למספר מרכזי' })).not.toBeInTheDocument()
      expect(api.called('PATCH', '/records/a')).toHaveLength(0)
    })
  })

  describe('doubtful and probable fields', () => {
    const record = () => makeRecord('a', {
      first_name: field('דנה', 'medium'),                               // printed, nothing verified it
      last_name: field('כהן', 'medium'),
      central_numbers: [field('939376', 'low', ['כתב יד'])],             // handwriting: doubtful
    })
    const levelOf = (label: string) => rowOf(label).dataset.level

    it('shows a field that was read from print more calmly than a doubtful one, and both still need a look', async () => {
      installFakeApi([record()])
      renderWithClient(<Harness id="a" />)
      await screen.findByText('דנה')
      expect(levelOf('שם פרטי')).toBe('medium')
      expect(levelOf('מספר מרכזי')).toBe('low')
      expect(levelOf('ת"ז')).toBe('ok')
      expect(isFlagged('שם פרטי') && isFlagged('מספר מרכזי')).toBe(true)
      expect(within(rowOf('שם פרטי')).getByText('לבדיקה קלה')).toBeInTheDocument()
      expect(within(rowOf('מספר מרכזי')).getByText('לבדיקה')).toBeInTheDocument()
    })

    it('confirms every probable field with one click and leaves the doubtful one alone', async () => {
      const api = installFakeApi([record()])
      renderWithClient(<Harness id="a" />)
      await screen.findByText('דנה')
      expect(screen.getByText('2 שדות נקראו בבירור אך לא אומתו')).toBeInTheDocument()
      await userEvent.setup().click(screen.getByRole('button', { name: 'אשרי את כולם' }))

      await waitFor(() => expect(api.called('PATCH', '/records/a')).toHaveLength(1))
      expect(api.called('PATCH', '/records/a')[0].body).toEqual({ first_name: 'דנה', last_name: 'כהן' })
      await waitFor(() => expect(levelOf('שם פרטי')).toBe('ok'))
      expect(levelOf('מספר מרכזי')).toBe('low')
      expect(screen.queryByRole('button', { name: 'אשרי את כולם' })).not.toBeInTheDocument()
    })

    it('offers nothing to confirm in bulk when every flagged field is doubtful', async () => {
      installFakeApi([flaggedRecord('a', 'רונן')])
      renderWithClient(<Harness id="a" />)
      await screen.findByText('רונן')
      expect(screen.queryByRole('button', { name: 'אשרי את כולם' })).not.toBeInTheDocument()
    })
  })
})
