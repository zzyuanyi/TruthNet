mysqldump: [Warning] Using a password on the command line interface can be insecure.
-- MySQL dump 10.13  Distrib 8.0.46, for Win64 (x86_64)
--
-- Host: localhost    Database: truthnet
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
mysqldump: Error: 'Access denied; you need (at least one of) the PROCESS privilege(s) for this operation' when trying to dump tablespaces

--
-- Table structure for table `companies`
--

DROP TABLE IF EXISTS `companies`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `companies` (
  `entity_id` varchar(64) NOT NULL COMMENT '内部稳定实体 ID',
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码，如 600519.SH',
  `sec_name` varchar(128) NOT NULL COMMENT '证券简称',
  `aliases` json DEFAULT NULL COMMENT '曾用名和别名',
  `exchange_code` varchar(16) DEFAULT NULL COMMENT '交易所代码: XSHG/XSHE',
  `industry_l1` varchar(64) DEFAULT NULL COMMENT '申万一级行业',
  `industry_l2` varchar(64) DEFAULT NULL COMMENT '申万二级行业',
  `sw_indu_code` varchar(32) DEFAULT NULL COMMENT '申万行业代码',
  `comp_type_code` smallint DEFAULT NULL COMMENT '公司类型',
  `listing_date` date DEFAULT NULL COMMENT '上市日期',
  `industry_source` varchar(64) DEFAULT NULL COMMENT '行业分类来源',
  `industry_as_of` date DEFAULT NULL COMMENT '行业分类有效日期',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`entity_id`),
  UNIQUE KEY `ix_companies_wind_code` (`wind_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `companies`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `companies` DISABLE KEYS */;
INSERT INTO `companies` (`entity_id`, `wind_code`, `sec_name`, `aliases`, `exchange_code`, `industry_l1`, `industry_l2`, `sw_indu_code`, `comp_type_code`, `listing_date`, `industry_source`, `industry_as_of`, `source_record_id`, `source_file`, `source_row`, `source_type`, `dataset_version`, `revision_no`, `is_latest`, `ingested_at`, `updated_at`, `quality_flags`, `checksum`) VALUES ('600518','600518.SH','康美药业',NULL,'XSHG','医药生物','中药Ⅱ',NULL,NULL,NULL,'akshare','2026-07-22',NULL,'industry_mapping.csv',3416,'industry_mapping','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL);
/*!40000 ALTER TABLE `companies` ENABLE KEYS */;

--
-- Table structure for table `balance_sheet`
--

DROP TABLE IF EXISTS `balance_sheet`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `balance_sheet` (
  `id` int NOT NULL AUTO_INCREMENT,
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `report_period` varchar(10) NOT NULL COMMENT '报告期 (YYYY-MM-DD)',
  `statement_type` varchar(32) NOT NULL COMMENT '报表类型代码',
  `ann_dt` varchar(10) DEFAULT NULL COMMENT '公告日期 (YYYY-MM-DD)',
  `monetary_cap` float DEFAULT NULL COMMENT '货币资金',
  `acct_rcv` float DEFAULT NULL COMMENT '应收账款',
  `oth_rcv` float DEFAULT NULL COMMENT '其他应收款',
  `inventories` float DEFAULT NULL COMMENT '存货',
  `tot_cur_assets` float DEFAULT NULL COMMENT '流动资产合计',
  `fix_assets` float DEFAULT NULL COMMENT '固定资产',
  `goodwill` float DEFAULT NULL COMMENT '商誉',
  `tot_assets` float DEFAULT NULL COMMENT '资产总计',
  `st_borrow` float DEFAULT NULL COMMENT '短期借款',
  `lt_borrow` float DEFAULT NULL COMMENT '长期借款',
  `acct_payable` float DEFAULT NULL COMMENT '应付账款',
  `tot_cur_liab` float DEFAULT NULL COMMENT '流动负债合计',
  `tot_liab` float DEFAULT NULL COMMENT '负债合计',
  `tot_shrhldr_eqy_incl_min_int` float DEFAULT NULL COMMENT '所有者权益合计（含少数股东权益）',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_bs_report` (`wind_code`,`report_period`,`statement_type`,`ann_dt`,`revision_no`),
  KEY `ix_balance_sheet_report_period` (`report_period`),
  KEY `ix_balance_sheet_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=39020 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `balance_sheet`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `balance_sheet` DISABLE KEYS */;
INSERT INTO `balance_sheet` (`id`, `wind_code`, `report_period`, `statement_type`, `ann_dt`, `monetary_cap`, `acct_rcv`, `oth_rcv`, `inventories`, `tot_cur_assets`, `fix_assets`, `goodwill`, `tot_assets`, `st_borrow`, `lt_borrow`, `acct_payable`, `tot_cur_liab`, `tot_liab`, `tot_shrhldr_eqy_incl_min_int`, `source_record_id`, `source_file`, `source_row`, `source_type`, `dataset_version`, `revision_no`, `is_latest`, `ingested_at`, `updated_at`, `quality_flags`, `checksum`) VALUES (34798,'600518.SH','20231231','408006000','20240413',826416000,1680320000,9539640000,699301000,12912600000,NULL,NULL,17045200000,NULL,NULL,1024590000,3888520000,5198100000,11847100000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(31623,'600518.SH','20240331','408006000','20240430',89146800,1786180000,NULL,796478000,12971000000,NULL,NULL,17094400000,NULL,NULL,1084800000,3979130000,5284740000,11809700000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(27035,'600518.SH','20240630','408006000','20240824',98860000,1803980000,10141400000,802515000,13043600000,NULL,NULL,17141100000,NULL,NULL,1160460000,4048930000,5339660000,11801400000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(24639,'600518.SH','20240930','408006000','20241031',171469000,1806340000,NULL,803653000,13024500000,NULL,NULL,17105100000,NULL,NULL,1253490000,4274470000,5331450000,11773600000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(20293,'600518.SH','20241231','408006000','20250419',142251000,1859980000,10243600000,624568000,13051800000,NULL,NULL,16927300000,NULL,NULL,1271930000,4750190000,4928480000,11998800000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(16318,'600518.SH','20250331','408006000','20250430',167339000,1897000000,NULL,606857000,13064200000,NULL,NULL,16945200000,NULL,NULL,1227610000,4772230000,4940610000,12004600000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(13398,'600518.SH','20250630','408006000','20250830',134687000,2078220000,10272800000,549359000,13191500000,NULL,NULL,17052000000,NULL,NULL,1282010000,4874440000,5034530000,12017500000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(8057,'600518.SH','20250930','408006000','20251031',154289000,2057110000,NULL,616818000,13438800000,NULL,NULL,17266000000,NULL,NULL,1420180000,5116490000,5268550000,11997400000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(5200,'600518.SH','20251231','408006000','20260418',449745000,1921600000,10246700000,546548000,13388000000,NULL,NULL,17187300000,NULL,NULL,1367790000,4796240000,4946520000,12240700000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(269,'600518.SH','20260331','408006000','20260430',432366000,1976120000,NULL,545781000,13286300000,NULL,NULL,17069100000,NULL,NULL,1346620000,4740820000,4884130000,12185000000,NULL,'4/asharebalancesheet_202605261517.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL);
/*!40000 ALTER TABLE `balance_sheet` ENABLE KEYS */;

--
-- Table structure for table `income_statement`
--

DROP TABLE IF EXISTS `income_statement`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `income_statement` (
  `id` int NOT NULL AUTO_INCREMENT,
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `report_period` varchar(10) NOT NULL COMMENT '报告期',
  `statement_type` varchar(32) NOT NULL COMMENT '报表类型代码',
  `ann_dt` varchar(10) DEFAULT NULL COMMENT '公告日期',
  `oper_rev` float DEFAULT NULL COMMENT '营业收入',
  `tot_oper_rev` float DEFAULT NULL COMMENT '营业总收入',
  `less_oper_cost` float DEFAULT NULL COMMENT '营业成本',
  `less_selling_dist_exp` float DEFAULT NULL COMMENT '销售费用',
  `less_gerl_admin_exp` float DEFAULT NULL COMMENT '管理费用',
  `less_fin_exp` float DEFAULT NULL COMMENT '财务费用',
  `oper_profit` float DEFAULT NULL COMMENT '营业利润',
  `tot_profit` float DEFAULT NULL COMMENT '利润总额',
  `net_profit_excl_min_int_inc` float DEFAULT NULL COMMENT '净利润（不含少数股东损益）',
  `net_profit_after_ded_nr_lp` float DEFAULT NULL COMMENT '归母净利润',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_is_report` (`wind_code`,`report_period`,`statement_type`,`ann_dt`,`revision_no`),
  KEY `ix_income_statement_report_period` (`report_period`),
  KEY `ix_income_statement_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=38211 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `income_statement`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `income_statement` DISABLE KEYS */;
INSERT INTO `income_statement` (`id`, `wind_code`, `report_period`, `statement_type`, `ann_dt`, `oper_rev`, `tot_oper_rev`, `less_oper_cost`, `less_selling_dist_exp`, `less_gerl_admin_exp`, `less_fin_exp`, `oper_profit`, `tot_profit`, `net_profit_excl_min_int_inc`, `net_profit_after_ded_nr_lp`, `source_record_id`, `source_file`, `source_row`, `source_type`, `dataset_version`, `revision_no`, `is_latest`, `ingested_at`, `updated_at`, `quality_flags`, `checksum`) VALUES (35221,'600518.SH','20231231','408006000','20240413',2184220000,2184220000,1945950000,258938000,138725000,-18933600,-126332000,-125586000,-123725000,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(31457,'600518.SH','20240331','408006000','20240430',544942000,544942000,483980000,60878700,47133100,-662272,-37555800,-37745700,-37377900,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(29559,'600518.SH','20240630','408006000','20240824',1114640000,1114640000,990797000,123813000,87118300,-567992,-47013500,-47318800,-46258500,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(23713,'600518.SH','20240930','408006000','20241031',1771620000,1771620000,1599780000,195463000,136028000,-1232700,-117416000,-64076400,-62715100,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(18207,'600518.SH','20241231','408006000','20250419',2427730000,2427730000,2206850000,243457000,193500000,-3383380,-4514060,36021300,33741300,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(15468,'600518.SH','20250331','408006000','20250430',596986000,596986000,496328000,58649900,36190500,146722,4478960,5850600,5753190,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(10530,'600518.SH','20250630','408006000','20250830',1262440000,1262440000,1052130000,131811000,81983600,-566649,18541700,19224500,19245400,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(7427,'600518.SH','20250930','408006000','20251031',1962410000,1962410000,1636010000,206723000,131036000,-627963,-2228330,-1023800,-753766,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(3154,'600518.SH','20251231','408006000','20260418',2598660000,2598660000,2142880000,275125000,189254000,-1236530,101603000,138425000,138545000,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(93,'600518.SH','20260331','408006000','20260430',543078000,543078000,427937000,54763300,42912400,-496699,-55805800,-55964600,-55772300,NULL,NULL,'4/ashareincome_202605261519.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL);
/*!40000 ALTER TABLE `income_statement` ENABLE KEYS */;

--
-- Table structure for table `cash_flow`
--

DROP TABLE IF EXISTS `cash_flow`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cash_flow` (
  `id` int NOT NULL AUTO_INCREMENT,
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `report_period` varchar(10) NOT NULL COMMENT '报告期',
  `statement_type` varchar(32) NOT NULL COMMENT '报表类型代码',
  `ann_dt` varchar(10) DEFAULT NULL COMMENT '公告日期',
  `net_cash_flows_oper_act` float DEFAULT NULL COMMENT '经营活动现金流量净额',
  `net_cash_flows_inv_act` float DEFAULT NULL COMMENT '投资活动现金流量净额',
  `net_cash_flows_fnc_act` float DEFAULT NULL COMMENT '筹资活动现金流量净额',
  `net_incr_cash_cash_equ` float DEFAULT NULL COMMENT '现金及等价物净增加额',
  `free_cash_flow` float DEFAULT NULL COMMENT '自由现金流',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cf_report` (`wind_code`,`report_period`,`statement_type`,`ann_dt`,`revision_no`),
  KEY `ix_cash_flow_report_period` (`report_period`),
  KEY `ix_cash_flow_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=39986 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cash_flow`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `cash_flow` DISABLE KEYS */;
INSERT INTO `cash_flow` (`id`, `wind_code`, `report_period`, `statement_type`, `ann_dt`, `net_cash_flows_oper_act`, `net_cash_flows_inv_act`, `net_cash_flows_fnc_act`, `net_incr_cash_cash_equ`, `free_cash_flow`, `source_record_id`, `source_file`, `source_row`, `source_type`, `dataset_version`, `revision_no`, `is_latest`, `ingested_at`, `updated_at`, `quality_flags`, `checksum`) VALUES (37611,'600518.SH','20231231','408006000','20240413',-359550000,-39255700,-47520700,-446327000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(32053,'600518.SH','20240331','408006000','20240430',-724575000,-3800800,-8895510,-737271000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(29709,'600518.SH','20240630','408006000','20240824',-743195000,-10398900,-14793100,-768387000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(25210,'600518.SH','20240930','408006000','20241031',-707050000,-2945920,-24791900,-734788000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(20180,'600518.SH','20241231','408006000','20250419',-887649000,91209800,63979700,-732459000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(16311,'600518.SH','20250331','408006000','20250430',39372000,-2276440,-6797250,30298300,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(12655,'600518.SH','20250630','408006000','20250830',36160400,-8710030,-12823200,14627100,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(7694,'600518.SH','20250930','408006000','20251031',-6230700,-9651900,28445700,12563100,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(4975,'600518.SH','20251231','408006000','20260418',149356000,8691050,121842000,279889000,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(640,'600518.SH','20260331','408006000','20260430',-17696600,-4350460,-5174900,-27221900,NULL,NULL,'4/asharecashflow_202605261518.csv',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL);
/*!40000 ALTER TABLE `cash_flow` ENABLE KEYS */;

--
-- Table structure for table `top_shareholders`
--

DROP TABLE IF EXISTS `top_shareholders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `top_shareholders` (
  `id` int NOT NULL AUTO_INCREMENT,
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `ann_dt` varchar(10) DEFAULT NULL COMMENT '公告日期',
  `s_holder_enddate` varchar(10) DEFAULT NULL COMMENT '股东持股截止日期',
  `s_holder_name` varchar(256) NOT NULL COMMENT '股东名称',
  `s_holder_aname` varchar(256) DEFAULT NULL COMMENT '股东别名（用于实体对齐）',
  `s_holder_pct` float DEFAULT NULL COMMENT '持股比例 (%)',
  `s_holder_quantity` float DEFAULT NULL COMMENT '持股数量',
  `s_holder_holdercategory` varchar(64) DEFAULT NULL COMMENT '股东类别',
  `s_holder_sequence` int DEFAULT NULL COMMENT '股东序号',
  `report_period` varchar(10) DEFAULT NULL COMMENT '报告期',
  `holder_entity_id` varchar(64) DEFAULT NULL COMMENT '股东实体 ID（与 companies.entity_id 对齐）',
  `entity_match_confidence` float DEFAULT NULL COMMENT '实体对齐置信度 (0-1)',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  KEY `ix_top_shareholders_holder_entity_id` (`holder_entity_id`),
  KEY `ix_top_shareholders_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=646450 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `top_shareholders`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `top_shareholders` DISABLE KEYS */;
INSERT INTO `top_shareholders` (`id`, `wind_code`, `ann_dt`, `s_holder_enddate`, `s_holder_name`, `s_holder_aname`, `s_holder_pct`, `s_holder_quantity`, `s_holder_holdercategory`, `s_holder_sequence`, `report_period`, `holder_entity_id`, `entity_match_confidence`, `source_record_id`, `source_file`, `source_row`, `source_type`, `dataset_version`, `revision_no`, `is_latest`, `ingested_at`, `updated_at`, `quality_flags`, `checksum`) VALUES (30444,'600518.SH','20240413','20231231','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',1.07,148000000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30445,'600518.SH','20240413','20231231','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司',1.18,163613000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30446,'600518.SH','20240413','20231231','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',1.31,181818000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30447,'600518.SH','20240413','20231231','中国民生银行股份有限公司','中国民生银行股份有限公司深圳分行',1.32,183388000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30448,'600518.SH','20240413','20231231','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',1.34,186350000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30449,'600518.SH','20240413','20231231','优质精选上市公司投资单一资金信托','五矿国际信托有限公司-五矿信托-优质精选上市公司投资单一资金信托',1.67,231901000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30450,'600518.SH','20240413','20231231','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',2.92,405074000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30451,'600518.SH','20240413','20231231','康美实业投资控股有限公司','康美实业投资控股有限公司',4.04,560220000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30452,'600518.SH','20240413','20231231','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',4.71,653207000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(30453,'600518.SH','20240413','20231231','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20231231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116313,'600518.SH','20240430','20240331','优质精选上市公司投资单一资金信托','五矿国际信托有限公司-五矿信托-优质精选上市公司投资单一资金信托',1.03,142591000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116314,'600518.SH','20240430','20240331','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',1.07,148000000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116315,'600518.SH','20240430','20240331','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司',1.18,163613000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116316,'600518.SH','20240430','20240331','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',1.31,181818000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116317,'600518.SH','20240430','20240331','中国民生银行股份有限公司','中国民生银行股份有限公司深圳分行',1.32,183388000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116318,'600518.SH','20240430','20240331','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',1.34,186350000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116319,'600518.SH','20240430','20240331','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',2.92,405074000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116320,'600518.SH','20240430','20240331','康美实业投资控股有限公司','康美实业投资控股有限公司',3.26,452220000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116321,'600518.SH','20240430','20240331','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',4.71,653207000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(116322,'600518.SH','20240430','20240331','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20240331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152977,'600518.SH','20240824','20240630','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152978,'600518.SH','20240824','20240630','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司','华安未来资产-民生银行-深圳市前海重明万方股权投资有限公司',0.84,116939000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152979,'600518.SH','20240824','20240630','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',1.07,148000000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152980,'600518.SH','20240824','20240630','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',1.31,181818000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152981,'600518.SH','20240824','20240630','中国民生银行股份有限公司','中国民生银行股份有限公司深圳分行',1.32,183388000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152982,'600518.SH','20240824','20240630','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',1.34,186350000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152983,'600518.SH','20240824','20240630','康美实业投资控股有限公司','康美实业投资控股有限公司',2.25,311426000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152984,'600518.SH','20240824','20240630','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',2.92,405074000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152985,'600518.SH','20240824','20240630','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',4.71,653207000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(152986,'600518.SH','20240824','20240630','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20240630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241690,'600518.SH','20241031','20240930','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241691,'600518.SH','20241031','20240930','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241692,'600518.SH','20241031','20240930','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',0.87,120983000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241693,'600518.SH','20241031','20240930','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',1.18,163791000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241694,'600518.SH','20241031','20240930','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',1.31,181818000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241695,'600518.SH','20241031','20240930','中国民生银行股份有限公司','中国民生银行股份有限公司深圳分行',1.32,183388000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241696,'600518.SH','20241031','20240930','康美实业投资控股有限公司','康美实业投资控股有限公司',1.67,231426000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241697,'600518.SH','20241031','20240930','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',2.92,405074000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241698,'600518.SH','20241031','20240930','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',4.71,653207000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(241699,'600518.SH','20241031','20240930','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20240930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290682,'600518.SH','20250419','20241231','张宇','张宇',0.58,80000000,'1',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290683,'600518.SH','20250419','20241231','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.67,93377600,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290684,'600518.SH','20250419','20241231','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',0.69,94982700,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290685,'600518.SH','20250419','20241231','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290686,'600518.SH','20250419','20241231','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290687,'600518.SH','20250419','20241231','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',0.77,106276000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290688,'600518.SH','20250419','20241231','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',1.08,149818000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290689,'600518.SH','20250419','20241231','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.61,223809000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290690,'600518.SH','20250419','20241231','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.72,515252000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(290691,'600518.SH','20250419','20241231','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20241231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381809,'600518.SH','20250430','20250331','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',0.77,106276000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381810,'600518.SH','20250430','20250331','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381811,'600518.SH','20250430','20250331','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.72,515252000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381812,'600518.SH','20250430','20250331','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.36,188383000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381813,'600518.SH','20250430','20250331','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381814,'600518.SH','20250430','20250331','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',0.73,101818000,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381815,'600518.SH','20250430','20250331','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381816,'600518.SH','20250430','20250331','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',0.69,94982700,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381817,'600518.SH','20250430','20250331','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.67,93377600,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(381818,'600518.SH','20250430','20250331','博时基金灵活配置5号特定多个客户资产管理计划','博时基金-工商银行-博时-工行-灵活配置5号特定多个客户资产管理计划',0.57,79416900,'2',NULL,'20250331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453353,'600518.SH','20250830','20250630','粤财信托·广发兴财康1号单一资金信托','广东粤财信托有限公司-粤财信托·广发兴财康1号单一资金信托',0.39,53818100,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453354,'600518.SH','20250830','20250630','博时基金灵活配置5号特定多个客户资产管理计划','博时基金-工商银行-博时-工行-灵活配置5号特定多个客户资产管理计划',0.57,79416900,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453355,'600518.SH','20250830','20250630','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.67,93377600,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453356,'600518.SH','20250830','20250630','长安宁-康美药业股权收益权买入返售集合资金信托计划','长安国际信托股份有限公司-长安宁-康美药业股权收益权买入返售集合资金信托计划',0.69,94982700,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453357,'600518.SH','20250830','20250630','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453358,'600518.SH','20250830','20250630','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453359,'600518.SH','20250830','20250630','中国光大银行股份有限公司','中国光大银行股份有限公司深圳分行',0.77,106276000,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453361,'600518.SH','20250830','20250630','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.32,182392000,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453362,'600518.SH','20250830','20250630','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.72,515252000,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(453918,'600518.SH','20250830','20250630','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.31,3509410000,'2',NULL,'20250630',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503222,'600518.SH','20251031','20250930','姜作军','姜作军',0.25,34200800,'1',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503223,'600518.SH','20251031','20250930','中融人寿保险股份有限公司-分红保险产品','中融人寿保险股份有限公司-分红产品',0.34,46806400,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503224,'600518.SH','20251031','20250930','香港中央結算有限公司','香港中央结算有限公司(陆股通)',0.57,78286900,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503225,'600518.SH','20251031','20250930','博时基金灵活配置5号特定多个客户资产管理计划','博时基金-工商银行-博时-工行-灵活配置5号特定多个客户资产管理计划',0.57,79416900,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503226,'600518.SH','20251031','20250930','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.68,93377600,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503227,'600518.SH','20251031','20250930','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503228,'600518.SH','20251031','20250930','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503229,'600518.SH','20251031','20250930','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.32,182392000,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503230,'600518.SH','20251031','20250930','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.73,515252000,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(503231,'600518.SH','20251031','20250930','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.38,3509410000,'2',NULL,'20250930',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552367,'600518.SH','20260418','20251231','姜作军','姜作军',0.27,37869100,'1',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552384,'600518.SH','20260418','20251231','香港中央結算有限公司','香港中央结算有限公司(陆股通)',0.33,45810600,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552385,'600518.SH','20260418','20251231','中融人寿保险股份有限公司-分红保险产品','中融人寿保险股份有限公司-分红产品',0.34,46806400,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552386,'600518.SH','20260418','20251231','博时基金灵活配置5号特定多个客户资产管理计划','博时基金-工商银行-博时-工行-灵活配置5号特定多个客户资产管理计划',0.57,79416900,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552387,'600518.SH','20260418','20251231','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.68,93377600,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552388,'600518.SH','20260418','20251231','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552389,'600518.SH','20260418','20251231','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552390,'600518.SH','20260418','20251231','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.32,182392000,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552391,'600518.SH','20260418','20251231','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.22,444878000,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(552392,'600518.SH','20260418','20251231','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.38,3509410000,'2',NULL,'20251231',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636310,'600518.SH','20260430','20260331','姜作军','姜作军',0.27,37869100,'1',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636311,'600518.SH','20260430','20260331','中融人寿保险股份有限公司-分红保险产品','中融人寿保险股份有限公司-分红产品',0.34,46806400,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636312,'600518.SH','20260430','20260331','博时基金灵活配置5号特定多个客户资产管理计划','博时基金-工商银行-博时-工行-灵活配置5号特定多个客户资产管理计划',0.57,79416900,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636313,'600518.SH','20260430','20260331','香港中央結算有限公司','香港中央结算有限公司(陆股通)',0.63,87106200,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636314,'600518.SH','20260430','20260331','中国农业银行股份有限公司','中国农业银行股份有限公司深圳市分行',0.68,93377600,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636315,'600518.SH','20260430','20260331','天津市鲲鹏融创企业管理咨询有限公司','天津市鲲鹏融创企业管理咨询有限公司',0.71,98167500,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636316,'600518.SH','20260430','20260331','上海浦东发展银行股份有限公司','上海浦东发展银行股份有限公司深圳分行',0.75,103542000,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636317,'600518.SH','20260430','20260331','康美药业股份有限公司破产企业财产处置专用账户','康美药业股份有限公司破产企业财产处置专用账户',1.32,182392000,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636318,'600518.SH','20260430','20260331','中国建设银行股份有限公司','中国建设银行股份有限公司广东省分行',3.22,444878000,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL),(636319,'600518.SH','20260430','20260331','广东神农氏企业管理合伙企业(有限合伙)','广东神农氏企业管理合伙企业(有限合伙)',25.38,3509410000,'2',NULL,'20260331',NULL,NULL,NULL,'2/clean.xlsx',NULL,'competition_data','competition-2026',1,1,'2026-07-22 16:10:09','2026-07-22 16:10:09',NULL,NULL);
/*!40000 ALTER TABLE `top_shareholders` ENABLE KEYS */;

--
-- Table structure for table `announcements`
--

DROP TABLE IF EXISTS `announcements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `announcements` (
  `id` int NOT NULL AUTO_INCREMENT,
  `object_id` varchar(128) NOT NULL COMMENT '公告源 ID',
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `ann_dt` varchar(10) DEFAULT NULL COMMENT '公告日期',
  `n_info_title` varchar(512) NOT NULL COMMENT '公告标题',
  `n_info_fcode` varchar(128) DEFAULT NULL,
  `sentiment` varchar(16) DEFAULT NULL COMMENT '情感: positive/negative/neutral',
  `sentiment_method` varchar(32) DEFAULT NULL COMMENT '情感分析方法',
  `source_uri` varchar(1024) DEFAULT NULL COMMENT '来源 URI',
  `content_hash` varchar(128) DEFAULT NULL COMMENT '内容哈希 (SHA-256)',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `object_id` (`object_id`),
  KEY `ix_announcements_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=7312 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `announcements`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `announcements` DISABLE KEYS */;
/*!40000 ALTER TABLE `announcements` ENABLE KEYS */;

--
-- Table structure for table `research_reports`
--

DROP TABLE IF EXISTS `research_reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `research_reports` (
  `id` int NOT NULL AUTO_INCREMENT,
  `report_id` varchar(128) NOT NULL COMMENT '研报唯一 ID',
  `wind_code` varchar(32) NOT NULL COMMENT 'Wind 代码',
  `sec_code` varchar(32) DEFAULT NULL COMMENT '证券代码',
  `exchange_code` varchar(16) DEFAULT NULL COMMENT '交易所代码',
  `sec_name` varchar(128) DEFAULT NULL COMMENT '证券简称',
  `org_name` varchar(256) DEFAULT NULL COMMENT '研究机构',
  `title` varchar(512) NOT NULL COMMENT '研报标题',
  `publish_date` varchar(10) DEFAULT NULL COMMENT '发布日期',
  `abstract` text COMMENT '摘要/核心观点',
  `rating_org` varchar(32) DEFAULT NULL COMMENT '原始评级',
  `rating_change` varchar(16) DEFAULT NULL COMMENT '评级变化: up/down/maintain',
  `industry_l1` varchar(64) DEFAULT NULL COMMENT '申万一级行业',
  `sw_indu_code` varchar(32) DEFAULT NULL COMMENT '申万行业代码',
  `source_uri` varchar(1024) DEFAULT NULL COMMENT '来源 URI',
  `content_hash` varchar(128) DEFAULT NULL COMMENT '内容哈希',
  `source_record_id` varchar(256) DEFAULT NULL COMMENT '原始记录 ID',
  `source_file` varchar(512) DEFAULT NULL COMMENT '来源文件名',
  `source_row` int DEFAULT NULL COMMENT '来源行号',
  `source_type` varchar(64) DEFAULT NULL COMMENT '来源类型',
  `dataset_version` varchar(64) DEFAULT NULL COMMENT '数据集版本',
  `revision_no` int NOT NULL COMMENT '修订版本号',
  `is_latest` tinyint(1) NOT NULL COMMENT '是否最新修订',
  `ingested_at` datetime NOT NULL COMMENT '入库时间',
  `updated_at` datetime NOT NULL COMMENT '最后更新时间',
  `quality_flags` json DEFAULT NULL COMMENT '数据质量标记',
  `checksum` varchar(128) DEFAULT NULL COMMENT '记录校验和 (SHA-256)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `report_id` (`report_id`),
  KEY `ix_research_reports_wind_code` (`wind_code`)
) ENGINE=InnoDB AUTO_INCREMENT=55215 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `research_reports`
--
-- WHERE:  wind_code='600518.SH'

/*!40000 ALTER TABLE `research_reports` DISABLE KEYS */;
/*!40000 ALTER TABLE `research_reports` ENABLE KEYS */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-07-23  0:19:59
