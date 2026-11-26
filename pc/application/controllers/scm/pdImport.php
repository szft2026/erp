<?php
/**
 * @author : zl
 * @email : 932460566@qq.com
 */
if (!defined('BASEPATH')) exit('No direct script access allowed');

class PdImport extends CI_Controller {

    public function __construct(){
        parent::__construct();
		$this->common_model->checkpurview();
		$this->load->library('excel/excel');
    }
	
	 
	public function index() {
	    $info = upload('file','./data/upfile/');
	    if (!is_array($info) || empty($info['path'])) {
	        str_alert(-1,'请选择要导入的盘点文件');
	    }
	    $xls = $info['path'];  
	    $this->excel->setOutputEncoding('utf-8');  
		$this->excel->read($xls); 
		$list = $this->excel->sheets[0]['cells'];
		foreach ($list as $arr=>$row) {
		    $data[$arr]['id']    = @$row['1'];  
			$data[$arr]['title'] = @$row['2'];  
			$data[$arr]['nr']    = @$row['3'];  
		}
		print_r($data); 
		//str_alert(-1,'文件写入失败');   
	}
	
    
}

/* End of file welcome.php */
/* Location: ./application/controllers/welcome.php */