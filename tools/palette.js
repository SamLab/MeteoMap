var RR_COLORS=[[0,[146,163,185,0]],[1,[146,161,181,.8]],[5,[103,104,158,1]],[11,[56,64,128,1]],[15,[29,175,87,1]],[30,[255,247,0,1]],[40,[255,174,0,1]],[47,[226,40,86,1]],[58,[169,10,158,1]],[60,[169,10,158,1]]];
var PAL=(function(){
  var n=700,s=document.createElement('canvas'),i=s.getContext('2d'),g=i.createLinearGradient(0,0,n,0);
  s.width=n;s.height=30;
  for(var a=0;a<RR_COLORS.length-1;a++)g.addColorStop(RR_COLORS[a][0]/70,'rgba('+RR_COLORS[a][1]+')');
  i.fillStyle=g;i.fillRect(0,0,n,30);
  return i.getImageData(0,0,n,1).data;
})();
