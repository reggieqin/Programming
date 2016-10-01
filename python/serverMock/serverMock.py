# -*- coding: utf-8 -*-

import protocol_pb2

def rechargeInfoMock_req(request, response):
	response.rechargeInfoResponse.rechargeInfo.firstRecharge = True
	rechargeDetail = response.rechargeInfoResponse.rechargeInfo.rechargeDetails.add()
	rechargeDetail.cash_num = 100
	rechargeDetail.cash_type = 1
	rechargeDetail.recharge_cnt = 3
	return response

def rechargeInfoMock_res(response):
	response.rechargeInfoResponse.rechargeInfo.rechargeDetails[0].cash_num = 300
	response.totalRechargeToken = 100000003
	return response

def userInstrusion_res(response):
	response.userIntrusionResponse.bossId = 10010
	return response

def silvermineAssist_req(request, response):
	response.error = protocol_pb2.Response.SILVERMINE_AUTO_FINDING_MINE
	return response

mock_api = {
	# Add your customized api here...
	protocol_pb2.Request.GET_RECHARGE_INFO : (0, None, rechargeInfoMock_res),
	protocol_pb2.Request.GET_INTRUSION : (0, None, userInstrusion_res),
	protocol_pb2.Request.SILVERMINE_TO_ASSIST_CAVE : (0, silvermineAssist_req, None),
}

