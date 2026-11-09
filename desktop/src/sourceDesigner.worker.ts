import { createSourceStems, type SourceControls, type SourceFamily } from './sourceDesigner'
self.onmessage = ({ data }: MessageEvent<{ controls: SourceControls; family: SourceFamily }>) => {
  try {
    const stems = createSourceStems(data.controls, undefined, data.family)
    self.postMessage({ stems }, { transfer: stems.flat().map(channel => channel.buffer) })
  } catch (error) {
    self.postMessage({ error: error instanceof Error ? error.message : 'Source generation failed.' })
  }
}
