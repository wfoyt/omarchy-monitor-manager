import QtQuick
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
  id: root
  moduleName: "local.monitor-layout"
  ipcTarget: "local.monitor-layout"
  manageIpc: false
  IpcHandler {
    target: "local.monitor-layout"
    function open(): void {root.open()}
    function close(): void {root.close()}
    function show(): void {root.open()}
    function hide(): void {root.close()}
    function toggle(): void {root.toggle()}
    function state(): string {return JSON.stringify({version:editor.implementationVersion,opened:root.opened,dragMoves:editor.dragMoveCount,primary:editor.primaryName,displays:editor.displays})}
  }
  property string helper: decodeURIComponent(Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, ""))
  property string pending: ""
  property bool received: false
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  function refresh() { if(!readProc.running && !previewProc.running && !primaryProc.running) {editor.loading=true; readProc.running=true} }
  function handle(data) {
    try {
      var event=JSON.parse(data)
      if(event.event==='error') {editor.message=event.message; editor.failed=true; return}
      if(event.event==='displays') {editor.load(event.displays); editor.primaryName=event.primary || ''; received=true}
      if(event.event==='primarySaved') {editor.primaryName=event.primary; editor.message='Primary monitor saved. Workspaces 1–10 now use '+event.primary+'.'; editor.failed=false}
      if(event.event==='preview') {editor.previewing=true; editor.seconds=event.seconds; editor.message=''; root.open()}
      if(event.event==='tick') editor.seconds=event.seconds
      if(event.event==='kept') {editor.previewing=false; editor.original=JSON.parse(JSON.stringify(editor.displays)); editor.message='Layout saved. Your previous configuration was backed up.'; editor.failed=false}
      if(event.event==='reverted') {editor.previewing=false; editor.displays=JSON.parse(JSON.stringify(editor.original)); if(!editor.failed) editor.message='Previous display settings restored.'}
    } catch(e) {editor.failed=true; editor.message='Could not read display information: '+String(e)}
  }
  onOpenedChanged: if(opened && !editor.dirty && !previewProc.running && !primaryProc.running) refresh()

  Process {
    id: readProc
    command: ["python3", root.helper, "read"]
    stdout: SplitParser { onRead: function(data) {root.handle(data)} }
    stderr: StdioCollector { id: readErrors }
    onExited: function(code) {editor.loading=false; if(code && !editor.failed) {editor.failed=true; editor.message=readErrors.text || 'Unable to read displays. Is Hyprland running?'} }
  }
  Process {
    id: previewProc
    command: ["python3", root.helper, "preview"]
    stdinEnabled: true
    // The worker outlives a QML reload long enough to restore the layout on EOF.
    onStarted: {write(root.pending+'\n'); root.pending=''}
    stdout: SplitParser { onRead: function(data) {root.handle(data)} }
    stderr: StdioCollector { id: previewErrors }
    onExited: function(code) {
      editor.busy=false; editor.previewing=false
      if(code && !editor.failed) {editor.failed=true; editor.message=previewErrors.text || 'The preview failed. Reload your displays and try again.'}
    }
  }
  Process {
    id: primaryProc
    property string selectedName: ""
    command: ["python3", root.helper, "primary"]
    stdinEnabled: true
    onStarted: write(selectedName+'\n')
    stdout: SplitParser { onRead: function(data) {root.handle(data)} }
    stderr: StdioCollector { id: primaryErrors }
    onExited: function(code) {editor.busy=false; if(code && !editor.failed) {editor.failed=true; editor.message=primaryErrors.text || 'Could not set the primary monitor.'} }
  }
  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰍺"
    tooltipText: "Monitor layout"
    onPressed: root.toggle()
  }
  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: editor
    contentWidth: panel.fittedContentWidth(Style.space(860))
    contentHeight: panel.cappedContentHeight(Style.space(790))
    EditorV2 {
      id: editor
      anchors.fill: parent
      onPrimaryRequested: function(name) {message='Setting primary monitor…'; failed=false; busy=true; primaryProc.selectedName=name; primaryProc.running=true}
      onReloadRequested: {message=''; failed=false; root.refresh()}
      onCloseRequested: root.close()
      onPreviewRequested: function(draft) {message=''; failed=false; busy=true; root.pending=JSON.stringify(draft); previewProc.running=true}
      onKeepRequested: {previewing=false; message='Saving layout…'; previewProc.write('keep\n')}
      onRevertRequested: {previewing=false; message='Restoring previous settings…'; previewProc.write('revert\n')}
    }
  }
}
