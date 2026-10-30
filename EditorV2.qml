import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import qs.Ui as Ui
import qs.Commons
import qs.Commons as Commons
import "Layout.js" as Geometry

FocusScope {
  id: root
  readonly property string implementationVersion: "1.1.0"
  property string primaryName: ""
  signal primaryRequested(string name)
  property int dragMoveCount: 0
  property var displays: []
  property var original: []
  property int selected: 0
  property bool loading: false
  property bool busy: false
  property bool previewing: false
  property int seconds: 20
  property string message: ""
  property bool failed: false
  readonly property var current: displays.length ? displays[Math.min(selected, displays.length-1)] : null
  readonly property bool dirty: JSON.stringify(displays) !== JSON.stringify(original)
  readonly property real unit: Style.effectiveSpacingScale
  readonly property color ink: Commons.Color.popups.text
  readonly property color accent: Commons.Color.accent
  signal reloadRequested()
  signal previewRequested(var draft)
  signal keepRequested()
  signal revertRequested()
  signal closeRequested()

  function load(list) { original = Geometry.copy(list); displays = Geometry.copy(list); selected = Math.min(selected, Math.max(0, list.length-1)) }
  function edit(fields) {
    if (busy || !current) return
    var list = Geometry.copy(displays)
    Object.keys(fields).forEach(function(k){list[root.selected][k] = fields[k]})
    displays = list
  }
  function resolution(value) {
    var dims = value.split('x'), w = Number(dims[0]), h = Number(dims[1])
    if(w===current.width && h===current.height) return
    var modes = current.modes.filter(function(m){return m.width===w && m.height===h})
    modes.sort(function(a,b){return Math.abs(a.rate-root.current.rate)-Math.abs(b.rate-root.current.rate)})
    edit({width:w, height:h, rate:modes[0].rate, scale:1})
  }
  Keys.onEscapePressed: { if (previewing) revertRequested(); else closeRequested() }

  component Label: Text {
    color: root.ink
    textFormat: Text.PlainText
    font.family: Style.font.family
    font.pixelSize: Style.font.body
    elide: Text.ElideRight
  }
  component Action: Ui.Button { focusable: true; bordered: true; foreground: root.ink }

  ColumnLayout {
    anchors.fill: parent
    spacing: Style.space(16)
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(12)
      Label { text: "󰍺"; font.pixelSize: Style.font.display; color: root.accent }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(3)
        Label { text: "Monitor layout"; font.pixelSize: Style.font.title * 1.35; font.bold: true }
        Label { text: "A workspace that fits your desk."; opacity: .65; Layout.fillWidth: true }
      }
      Action { text: "Reload"; tooltipText: "Read connected displays and discard edits"; enabled: !root.busy && !root.loading; onClicked: root.reloadRequested() }
      Ui.Button { text: "×"; focusable: true; fontSize: Style.font.title; tooltipText: "Close"; onClicked: root.closeRequested() }
    }

    RowLayout {
      Layout.fillWidth: true
      Label { text: "ARRANGEMENT"; font.pixelSize: Style.font.caption; font.bold: true; opacity: .6; Layout.fillWidth: true }
      Action {
        text: "Arrange in a row"; enabled: root.displays.length > 1 && !root.busy
        tooltipText: "Align top edges and place displays side by side"
        onClicked: root.displays = Geometry.row(root.displays)
      }
    }
    Rectangle {
      id: canvas
      Layout.fillWidth: true
      Layout.preferredHeight: Math.min(Style.space(250), Math.max(Style.space(100), root.height * .32))
      color: Util.alpha(root.ink, .025)
      border.color: Util.alpha(root.ink, .14)
      radius: Style.cornerRadius
      clip: true
      property bool dragging: false
      property var frozenBounds: ({x:0,y:0,w:1920,h:1080})
      readonly property var box: dragging ? frozenBounds : Geometry.bounds(root.displays)
      readonly property real factor: Math.min((width-Style.space(90))/box.w, (height-Style.space(64))/box.h, .3*root.unit)
      readonly property real originX: (width-box.w*factor)/2-box.x*factor
      readonly property real originY: (height-box.h*factor)/2-box.y*factor
      Repeater {
        model: Math.max(0, Math.floor(canvas.width/Style.space(20)))
        delegate: Rectangle {
          required property int index
          x: (index+1)*Style.space(20); y: 0; width: 1; height: canvas.height
          color: Util.alpha(root.ink, .025)
        }
      }
      Repeater {
        id: monitorTiles
        model: root.displays.length
        delegate: Rectangle {
          id: tile
          objectName: "monitorTile" + index
          required property int index
          readonly property var modelData: root.displays[index]
          readonly property var logical: Geometry.size(modelData)
          x: canvas.originX+modelData.x*canvas.factor
          y: canvas.originY+modelData.y*canvas.factor
          width: logical.w*canvas.factor
          height: logical.h*canvas.factor
          z: root.selected === index ? 2 : 1
          color: Util.alpha(root.selected===index ? root.accent : root.ink, root.selected===index ? .17 : .06)
          border.color: root.selected===index ? root.accent : Util.alpha(root.ink,.35)
          border.width: root.selected===index ? 2 : 1
          radius: Math.max(Style.cornerRadius, Style.space(3))
          activeFocusOnTab: true
          Accessible.role: Accessible.Button
          Accessible.name: "Display " + (index+1) + ", " + modelData.name + ". Arrow keys move; Shift moves one pixel."
          Keys.onPressed: function(event) {
            if (root.busy) return
            var delta = event.modifiers & Qt.ShiftModifier ? 1 : 10
            var dx = event.key===Qt.Key_Left ? -delta : event.key===Qt.Key_Right ? delta : 0
            var dy = event.key===Qt.Key_Up ? -delta : event.key===Qt.Key_Down ? delta : 0
            if(dx || dy) {root.selected=index; root.edit({x:modelData.x+dx,y:modelData.y+dy}); event.accepted=true}
          }
          Column {
            anchors.centerIn: parent
            width: Math.max(0,parent.width-Style.space(12))
            spacing: Style.space(4)
            Label { anchors.horizontalCenter: parent.horizontalCenter; text: String(tile.index+1).padStart(2,'0'); font.pixelSize: Math.min(Style.space(30),tile.height*.26); font.bold: true; color: root.selected===tile.index ? root.accent : root.ink }
            Label { width: parent.width; text: tile.modelData.name; horizontalAlignment: Text.AlignHCenter; font.pixelSize: Style.font.caption; visible: tile.height>Style.space(65) }
            Label { width: parent.width; text: Math.round(tile.modelData.scale*100)+"% · "+Geometry.formatRate(tile.modelData.rate)+" Hz"; horizontalAlignment: Text.AlignHCenter; font.pixelSize: Style.font.caption; opacity: .65; visible: tile.height>Style.space(100) }
          }

        }
      }
      // The canvas owns an exclusive pointer gesture independently of the
      // moving tiles. Qt's DragHandler handles mouse, touch and tablet grabs.
      Item {
        id: arrangementInput
        objectName: "arrangementInput"
        anchors.fill: parent
        z: 10
        enabled: !root.busy
        readonly property bool pressed: displayDrag.active || displayTap.pressed
        property point basePosition
        property real dragFactor: 1
        function tileAt(px, py) {
          var order=[]
          for(var i=root.displays.length-1;i>=0;i--) if(i!==root.selected) order.push(i)
          order.unshift(root.selected)
          for(var n=0;n<order.length;n++) {
            var tile=monitorTiles.itemAt(order[n])
            if(tile && px>=tile.x && px<=tile.x+tile.width && py>=tile.y && py<=tile.y+tile.height) return order[n]
          }
          return -1
        }
        function selectAt(px,py) {
          var index=tileAt(px,py)
          if(index<0) return -1
          root.selected=index
          monitorTiles.itemAt(index).forceActiveFocus()
          return index
        }
        function begin(px,py) {
          var index=selectAt(px,py)
          if(index<0) return
          canvas.frozenBounds=Geometry.bounds(root.displays)
          canvas.dragging=true
          basePosition=Qt.point(root.displays[index].x,root.displays[index].y)
          dragFactor=canvas.factor
          root.dragMoveCount=0
        }
        function move(dx,dy) {
          if(!canvas.dragging) return
          root.edit({x:Math.round(basePosition.x+dx/dragFactor),
                     y:Math.round(basePosition.y+dy/dragFactor)})
          root.dragMoveCount++
        }
        function finish() {
          if(!canvas.dragging) return
          var current=root.displays[root.selected]
          root.edit(Geometry.snap(root.displays,root.selected,current.x,current.y,Style.space(14)/dragFactor))
          canvas.dragging=false
        }
        HoverHandler { cursorShape: displayDrag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor }
        TapHandler {
          id: displayTap
          acceptedButtons: Qt.LeftButton
          onPressedChanged: if(pressed) arrangementInput.selectAt(point.pressPosition.x,point.pressPosition.y)
        }
        DragHandler {
          id: displayDrag
          target: null
          acceptedButtons: Qt.LeftButton
          dragThreshold: 0
          // Take exclusive ownership and do not approve any competing takeover.
          grabPermissions: PointerHandler.CanTakeOverFromAnything
          cursorShape: Qt.ClosedHandCursor
          onActiveChanged: {
            if(active) {
              arrangementInput.begin(centroid.pressPosition.x,centroid.pressPosition.y)
              arrangementInput.move(centroid.position.x-centroid.pressPosition.x,centroid.position.y-centroid.pressPosition.y)
            } else arrangementInput.finish()
          }
          onActiveTranslationChanged: if(active) arrangementInput.move(activeTranslation.x,activeTranslation.y)
        }
      }
      Label {
        anchors.centerIn: parent
        width: parent.width-Style.space(40)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        visible: !root.displays.length
        text: root.loading ? "Finding your displays…" : "No active displays found.\nReload to connect to Hyprland."
        opacity: .65
      }
      Label {
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.margins: Style.space(10)
        text: "Drag to arrange · edges snap into place"
        font.pixelSize: Style.font.caption; opacity: .5
        visible: root.displays.length > 0
      }
    }
    RowLayout {
      Layout.fillWidth: true
      Label {
        Layout.fillWidth: true
        text: "Primary: " + (root.primaryName || "Not configured")
        color: root.accent
        font.bold: true
      }
      Action {
        text: root.current && root.current.name===root.primaryName ? "Primary monitor" : "Make primary"
        enabled: !!root.current && root.current.name!==root.primaryName && !root.busy && !root.dirty && !root.loading
        tooltipText: "Save this display as the home of workspaces 1–10 and workspace shortcuts. The other display keeps the dedicated workspace. Finish layout edits first."
        onClicked: root.primaryRequested(root.current.name)
      }
    }
    Flow {
      Layout.fillWidth: true
      spacing: Style.space(6)
      Repeater {
        model: root.displays.length
        delegate: Ui.Button {
          required property int index
          readonly property var modelData: root.displays[index]
          text: (index+1)+"  "+modelData.name+(modelData.name===root.primaryName ? "  ★" : "")
          selected: index===root.selected; focusable: true; bordered: true
          onClicked: root.selected=index
        }
      }
    }
    Rectangle { Layout.fillWidth: true; height: 1; color: Util.alpha(root.ink,.13) }

    ScrollView {
      id: scroll
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
      ColumnLayout {
        width: scroll.availableWidth
        spacing: Style.space(14)
        ColumnLayout {
          Layout.fillWidth: true
          spacing: Style.space(14)
          visible: root.current!==null
          enabled: !root.busy
          RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
              Layout.fillWidth: true
              spacing: Style.space(3)
              Label { text: root.current ? root.current.name : ""; font.bold: true; color: root.accent }
              Label { text: root.current ? root.current.description : ""; opacity: .6; Layout.fillWidth: true; font.pixelSize: Style.font.caption }
            }
            Label { text: root.current ? Math.round(Geometry.size(root.current).w)+" × "+Math.round(Geometry.size(root.current).h)+" usable" : ""; opacity: .5; font.pixelSize: Style.font.caption }
          }
          GridLayout {
            Layout.fillWidth: true
            columns: root.width > Style.space(620) ? 3 : 1
            columnSpacing: Style.space(14)
            rowSpacing: Style.space(12)
            Ui.Dropdown { Layout.fillWidth: true; label: "Resolution"; value: root.current ? root.current.width+'x'+root.current.height : ''; options: Geometry.resolutions(root.current); onChanged: function(value){root.resolution(value)} }
            Ui.Dropdown { Layout.fillWidth: true; label: "Refresh rate"; value: root.current ? String(root.current.rate) : ''; options: Geometry.rates(root.current); onChanged: function(value){root.edit({rate:Number(value)})} }
            Ui.Dropdown { Layout.fillWidth: true; label: "Scale"; value: root.current ? String(root.current.scale) : ''; options: Geometry.scales(root.current); onChanged: function(value){root.edit({scale:Number(value)})} }
          }
          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(14)
            Ui.NumberField { label: "Horizontal position"; from: -32768; to: 32768; value: root.current ? root.current.x : 0; fieldWidth: Style.space(150); onModified: function(value){root.edit({x:value})} }
            Ui.NumberField { label: "Vertical position"; from: -32768; to: 32768; value: root.current ? root.current.y : 0; fieldWidth: Style.space(150); onModified: function(value){root.edit({y:value})} }
            Label { text: "Positions use scaled pixels.\nLarger scale makes content bigger."; opacity: .5; font.pixelSize: Style.font.caption; wrapMode: Text.WordWrap; elide: Text.ElideNone; Layout.fillWidth: true; Layout.alignment: Qt.AlignBottom }
          }
        }
      }
    }

    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: statusColumn.implicitHeight + Style.space(20)
      color: Util.alpha(root.previewing ? root.accent : root.failed ? Commons.Color.urgent : root.ink, .07)
      border.color: Util.alpha(root.previewing ? root.accent : root.failed ? Commons.Color.urgent : root.ink, .2)
      radius: Style.cornerRadius
      Column {
        id: statusColumn
        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
        anchors.margins: Style.space(12)
        spacing: Style.space(4)
        Label {
          width: parent.width
          text: root.previewing ? "Keep this layout? Reverting in "+root.seconds+"s" : root.message || (root.dirty ? "Ready to preview your changes" : "Your displays, just the way you like them")
          wrapMode: Text.WordWrap; elide: Text.ElideNone
          color: root.failed ? Commons.Color.urgent : root.previewing ? root.accent : root.ink
        }
        Label {
          width: parent.width
          text: root.previewing ? "Check every display. Keep changes to save for your next login." : "Changes are tested for 20 seconds before you save them."
          font.pixelSize: Style.font.caption; opacity: .6; wrapMode: Text.WordWrap; elide: Text.ElideNone
        }
      }
    }
    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(10)
      Label { text: root.previewing ? "PREVIEW ACTIVE" : root.dirty ? "UNSAVED CHANGES" : "ALL SET"; font.pixelSize: Style.font.caption; opacity: .5; Layout.fillWidth: true }
      Action {
        text: root.previewing ? "Revert" : "Reset edits"
        enabled: root.previewing || (root.dirty && !root.busy)
        onClicked: { if(root.previewing) root.revertRequested(); else {root.displays=Geometry.copy(root.original); root.message=''; root.failed=false} }
      }
      Ui.Button {
        text: root.previewing ? "Keep changes" : root.busy ? "Applying…" : "Preview changes"
        selected: true; bordered: true; focusable: true; foreground: root.accent
        enabled: root.previewing || (root.dirty && !root.busy && !root.loading)
        onClicked: { if(root.previewing) root.keepRequested(); else root.previewRequested(root.displays) }
      }
    }
  }
}
