import { fireEvent, render, renderHook, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ImageCanvas, ViewToolbar } from './ImageViewer'
import { useImageView } from './useImageView'

function Canvas({ pageId }: { pageId?: string }) {
  const view = useImageView('k')
  return <div style={{ height: 400 }}><ImageCanvas pageId={pageId} view={view} /></div>
}

describe('ImageCanvas', () => {
  it('says so when the form has no page image', () => {
    render(<Canvas />)
    expect(screen.getByText('אין תמונה לטופס')).toBeInTheDocument()
  })

  it('asks the API for the page image and shows a loading note until it arrives', () => {
    render(<Canvas pageId="p1" />)
    expect(screen.getByAltText('תמונת הטופס')).toHaveAttribute('src', '/api/pages/p1/image')
    expect(screen.getByText('טוען תמונה…')).toBeInTheDocument()
  })

  it('removes the loading note once the image has loaded', () => {
    render(<Canvas pageId="p1" />)
    const img = screen.getByAltText('תמונת הטופס')
    Object.defineProperty(img, 'naturalWidth', { value: 1650 })
    Object.defineProperty(img, 'naturalHeight', { value: 2350 })
    fireEvent.load(img)
    expect(screen.queryByText('טוען תמונה…')).not.toBeInTheDocument()
  })

  it('says the image is unavailable when it fails to load', () => {
    render(<Canvas pageId="p1" />)
    fireEvent.error(screen.getByAltText('תמונת הטופס'))
    expect(screen.getByText('התמונה לא זמינה')).toBeInTheDocument()
  })
})

describe('ViewToolbar', () => {
  function Toolbar({ onExpand }: { onExpand?: () => void }) {
    const view = useImageView('k')
    return <><ViewToolbar view={view} onExpand={onExpand} /><output data-testid="state">{`${view.fit}|${view.zoom}|${view.rotation}|${view.lens}`}</output></>
  }
  const state = () => screen.getByTestId('state').textContent

  it('zooms, fits, rotates and toggles the lens', () => {
    render(<Toolbar />)
    expect(state()).toBe('height|1|0|false')
    fireEvent.click(screen.getByRole('button', { name: 'הגדלה' }))
    expect(state()).toBe('height|1.25|0|false')
    fireEvent.click(screen.getByRole('button', { name: 'התאמה לרוחב' }))
    expect(state()).toBe('width|1|0|false')
    fireEvent.click(screen.getByRole('button', { name: 'זכוכית מגדלת' }))
    expect(state()).toBe('width|1|0|true')
    fireEvent.click(screen.getByRole('button', { name: 'סיבוב' }))
    expect(state()).toBe('width|1|90|false')
  })

  it('shows the expand button only when the screen can expand', () => {
    const { unmount } = render(<Toolbar />)
    expect(screen.queryByRole('button', { name: 'הרחבה למסך מלא' })).not.toBeInTheDocument()
    unmount()
    let expanded = 0
    render(<Toolbar onExpand={() => { expanded += 1 }} />)
    fireEvent.click(screen.getByRole('button', { name: 'הרחבה למסך מלא' }))
    expect(expanded).toBe(1)
  })

  it('the hook is usable on its own', () => {
    const { result } = renderHook(() => useImageView('x'))
    expect(result.current.fit).toBe('height')
  })
})
