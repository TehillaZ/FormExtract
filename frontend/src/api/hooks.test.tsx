import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { makeDocument, makeRecord, pageStatus } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { useActivePages, useRecords, useUpload } from './hooks'

function Probe() {
  const upload = useUpload()
  useActivePages()
  const { data = [] } = useRecords()
  return (
    <div>
      <button type="button" onClick={() => upload.mutate([new File(['x'], 'a.pdf')])}>send</button>
      <span data-testid="count">{data.length}</span>
    </div>
  )
}

describe('records appear after an upload even when reading finishes before the first refresh', () => {
  it('fetches the records again once the uploaded page has left the active list', async () => {
    const api = installFakeApi([])
    api.uploadResult = [makeDocument('d1', [pageStatus('p1', 1, 'pending')], { done: false })]
    renderWithClient(<Probe />)
    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('0'))

    // by the time the page list is asked, the page is already a record and the list is empty
    api.records.push(makeRecord('r1'))
    await userEvent.setup().click(screen.getByText('send'))

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'))
  })
})
