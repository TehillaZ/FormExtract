import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeDocument, pageStatus } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { UploadView } from './UploadView'

const pdf = (name = 'forms.pdf') => new File(['%PDF-1.4'], name, { type: 'application/pdf' })

async function upload(file: File) {
  await userEvent.upload(screen.getByLabelText('בחירת קבצים'), file)
}

describe('UploadView', () => {
  it('sends the chosen file and shows how far each page got', async () => {
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'ready', 'r1'), pageStatus('p2', 2, 'processing')], { filename: 'forms.pdf', done: false })
    api.uploadResult = [doc]
    api.documents.d1 = doc
    renderWithClient(<UploadView onReview={() => {}} />)

    await upload(pdf())

    expect(await screen.findByText('forms.pdf')).toBeInTheDocument()
    expect(screen.getByText('עמוד 1 · מוכן')).toBeInTheDocument()
    expect(screen.getByText('עמוד 2 · בעיבוד')).toBeInTheDocument()
    expect(screen.getByText('1 מתוך 2 עמודים מוכנים')).toBeInTheDocument()

    const sent = api.called('POST', '/documents')[0].body as FormData
    expect((sent.get('files') as File).name).toBe('forms.pdf')
  })

  it('sends several files in one request', async () => {
    const api = installFakeApi()
    api.uploadResult = []
    renderWithClient(<UploadView onReview={() => {}} />)
    await userEvent.upload(screen.getByLabelText('בחירת קבצים'), [pdf('a.pdf'), pdf('b.pdf')])
    await waitFor(() => expect(api.called('POST', '/documents')).toHaveLength(1))
    expect((api.called('POST', '/documents')[0].body as FormData).getAll('files')).toHaveLength(2)
  })

  it('tells the user when the file was uploaded before', async () => {
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'ready', 'r1')], { duplicate: true })
    api.uploadResult = [doc]
    api.documents.d1 = { ...doc, duplicate: false }   // like the real API: only the upload's answer says "duplicate"
    renderWithClient(<UploadView onReview={() => {}} />)
    await upload(pdf())
    expect(await screen.findByText('קובץ זהה כבר הועלה בעבר, לא עובד שוב')).toBeInTheDocument()
  })

  it('lets a failed page be tried again', async () => {
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'error')])
    api.uploadResult = [doc]
    api.documents.d1 = doc
    renderWithClient(<UploadView onReview={() => {}} />)
    await upload(pdf())

    expect(await screen.findByText('עמוד 1 · שגיאה')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'נסי שוב' }))
    await waitFor(() => expect(api.called('POST', '/pages/p1/reprocess')).toHaveLength(1))
  })

  it('shows the server message when the upload is rejected', async () => {
    const api = installFakeApi()
    api.uploadError = 'forms.pdf: לא ניתן לקרוא את הקובץ'
    renderWithClient(<UploadView onReview={() => {}} />)
    await upload(pdf())
    expect(await screen.findByRole('alert')).toHaveTextContent('לא ניתן לקרוא את הקובץ')
  })

  it('offers "to review" only after something was uploaded, and goes there', async () => {
    const onReview = vi.fn()
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'ready', 'r1')])
    api.uploadResult = [doc]
    api.documents.d1 = doc
    renderWithClient(<UploadView onReview={onReview} />)
    expect(screen.queryByRole('button', { name: 'לבדיקה' })).not.toBeInTheDocument()

    await upload(pdf())
    await userEvent.click(await screen.findByRole('button', { name: 'לבדיקה' }))
    expect(onReview).toHaveBeenCalled()
  })

  it('tells the page which form to show as soon as the upload is accepted, before any field is read', async () => {
    const onUploaded = vi.fn()
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'processing')], { done: false })
    api.uploadResult = [doc]
    api.documents.d1 = doc
    renderWithClient(<UploadView onReview={() => {}} onUploaded={onUploaded} />)
    await upload(pdf())
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('p1'))
  })

  it('does not jump to a file that was uploaded before', async () => {
    const onUploaded = vi.fn()
    const api = installFakeApi()
    api.uploadResult = [makeDocument('d1', [pageStatus('p1', 1, 'ready', 'r1')], { duplicate: true })]
    renderWithClient(<UploadView onReview={() => {}} onUploaded={onUploaded} />)
    await upload(pdf())
    await screen.findByText(/כבר הועלה בעבר/)
    expect(onUploaded).not.toHaveBeenCalled()
  })

  it('refreshes the records once a document has finished', async () => {
    const api = installFakeApi()
    const doc = makeDocument('d1', [pageStatus('p1', 1, 'ready', 'r1')])
    api.uploadResult = [doc]
    api.documents.d1 = doc
    const { client } = renderWithClient(<UploadView onReview={() => {}} />)
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await upload(pdf())
    await screen.findByText('עמוד 1 · מוכן')
    await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ['records'] }))
  })
})
