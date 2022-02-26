web3 = new Web3(window.ethereum)
window.ethereum.enable()

function convertFromHex(hex) {
    var hex = hex.toString();//force conversion
    var str = '';
    for (var i = 0; i < hex.length; i += 2)
        str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
    return str;
}

function convertToHex(str) {
    var hex = '';
    for(var i=0;i<str.length;i++) {
        hex += ''+str.charCodeAt(i).toString(16);
    }
    return hex;
}


async function buildTransaction(web3Instance, parent, to, tokens, bio) {
	account = (await web3Instance.eth.getAccounts())[0];
	data = {"from":account, "to":web3Instance.utils.toChecksumAddress(to), "bio": bio.replaceAll(" ", "%20"), "tokens":tokens, "parent": parent, "type": 0};
	strdata = JSON.stringify(data);
	hash = web3Instance.utils.soliditySha3(strdata);
	signature = await web3Instance.eth.personal.sign(strdata, account);
	tx = {"data": data, "sig": signature, "hash": hash, "nodeSigs": {}};
	toSend = convertToHex(JSON.stringify(tx));
	return toSend;
}