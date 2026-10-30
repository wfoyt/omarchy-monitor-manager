import QtQuick
import QtQuick.Window
import QtTest
import Quickshell
import "Plugin" as Plugin
ShellRoot {
  Window {
    id: window
    visible: true
    width: 920
    height: 810
    Plugin.EditorV2 { id: editor; anchors.fill: parent; anchors.margins: 24 }
    Timer {
      interval: 300
      running: true
      onTriggered: {
        try {
          testcase.runDragChecks()
          console.log("DRAG_TEST_PASS")
        } catch(e) { console.error("DRAG_TEST_FAIL",String(e)) }
        finally { Qt.quit() }
      }
    }
    TestCase {
      id: testcase
      name: "MonitorDrag"
      windowShown: true
      when: false
      function check(condition,message) { if(!condition) throw new Error(message) }
      function load() {
        editor.load([
          {name:'DP-1',description:'Acer',width:2560,height:1440,rate:320,x:0,y:0,scale:1.25,transform:0,modes:[{width:2560,height:1440,rate:320}]},
          {name:'HDMI-A-1',description:'XEC',width:1920,height:1080,rate:60,x:2048,y:0,scale:1,transform:0,modes:[{width:1920,height:1080,rate:60}]}])
        wait(100)
      }
      function drag(index,dx,dy) {
        var tile=findChild(editor,"monitorTile"+index)
        check(tile!==null,"Display tile exists")
        var start=tile.mapToItem(editor,tile.width/2,tile.height/2)
        var input=findChild(editor,"arrangementInput")
        var inputStart=input.mapToItem(editor,0,0)
        var previous=editor.displays[index].x
        var previousY=editor.displays[index].y
        mousePress(editor,start.x,start.y,Qt.LeftButton)
        check(input.pressed,"Arrangement owns the mouse press")
        for(var i=1;i<=12;i++) {
          mouseMove(editor,start.x+i*dx,start.y+i*dy,10,Qt.LeftButton)
          wait(5)
          check(input.pressed,"Arrangement lost the mouse grab at step "+i)
          var inputNow=input.mapToItem(editor,0,0)
          check(inputNow.x===inputStart.x && inputNow.y===inputStart.y,"Input surface moved during drag")
          if(i===2) wait(500) // Keep holding still, then continue without releasing.
          if(dx!==0) check((editor.displays[index].x-previous)*dx>0,"Horizontal drag stopped at step "+i)
          if(dy!==0) check((editor.displays[index].y-previousY)*dy>0,"Vertical drag stopped at step "+i)
          previous=editor.displays[index].x
          previousY=editor.displays[index].y
        }
        mouseRelease(editor,start.x+12*dx,start.y+12*dy,Qt.LeftButton)
        check(editor.dragMoveCount>=12,"All held mouse moves reached the editor")
        wait(50)
      }
      function runDragChecks() {
        console.log("horizontal"); load(); drag(0,5,0); drag(0,-5,0)
        console.log("vertical"); load(); drag(1,0,4); drag(1,0,-4)
        console.log("scrolling viewport"); window.height=600
        load(); drag(0,5,0)
        load(); drag(1,0,4)
      }
    }
  }
}
