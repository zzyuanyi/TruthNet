BEGIN TRANSACTION;
CREATE TABLE analysis_runs (
	run_id VARCHAR(64) NOT NULL, 
	trace_id VARCHAR(64) NOT NULL, 
	endpoint VARCHAR(64) NOT NULL, 
	company_codes JSON, 
	period VARCHAR(10), 
	statement_scope VARCHAR(32), 
	status VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (run_id)
);
INSERT INTO "analysis_runs" VALUES('run_29737854be12','9ec12fe1-377e-400c-8c22-eb752be222c4','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:49:11');
INSERT INTO "analysis_runs" VALUES('run_a2fbc7e119a8','751aed16-964f-4a98-9773-6135aa21988f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:50:59');
INSERT INTO "analysis_runs" VALUES('run_599f07b09a08','cd2203a4-f5a2-487c-9e4e-7d8e9fcc487a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:52:12');
INSERT INTO "analysis_runs" VALUES('run_02d855673d25','7aaa06ce-089d-42a4-b082-4d76012e4f67','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:53:46');
INSERT INTO "analysis_runs" VALUES('run_870f57145765','d4a7713a-6868-4273-9017-b1d2de156b2d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:55:19');
INSERT INTO "analysis_runs" VALUES('run_8ae4ed5d5917','9ca4f5c5-77c3-463a-83d3-6ed343ed2a50','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:56:52');
INSERT INTO "analysis_runs" VALUES('run_25041fb44140','e4708a2b-7f5e-4b0d-b686-4cae268f4b4f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:58:25');
INSERT INTO "analysis_runs" VALUES('run_33b6e8b4b452','1a66a9d0-5e61-40a8-91f6-76b623024519','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 06:59:58');
INSERT INTO "analysis_runs" VALUES('run_557fad02238c','9ab31516-1137-48eb-b1a5-e77e7b8a2b22','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:01:32');
INSERT INTO "analysis_runs" VALUES('run_05f67dd23ee0','31a6d83d-e455-4b97-9db2-59d8664f813f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:03:05');
INSERT INTO "analysis_runs" VALUES('run_1af3eb8f9f67','e78cb7d9-f9bd-40da-bbef-5b0c13f4ae28','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:04:33');
INSERT INTO "analysis_runs" VALUES('run_2dc7715541b3','6b99caf9-78a7-40cc-b94e-1a61a426be7f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:04:34');
INSERT INTO "analysis_runs" VALUES('run_0fce4bebe921','64d7e594-52a9-4bed-939b-d405d4952fa1','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:04:38');
INSERT INTO "analysis_runs" VALUES('run_c4289c191f59','d1d27c34-6dbf-4803-9263-00cfc6fab592','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:04:39');
INSERT INTO "analysis_runs" VALUES('run_dc96be9f2065','0a96abf9-b323-4068-83c4-9ca9306896a1','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:04:41');
INSERT INTO "analysis_runs" VALUES('run_9864b1586b32','495ea06c-30cc-45ee-9544-cdd4452b2519','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:06:12');
INSERT INTO "analysis_runs" VALUES('run_eab1f9c72818','5f6f7555-d09d-4018-9296-59807b1a7506','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:07:23');
INSERT INTO "analysis_runs" VALUES('run_ddb79d358109','d4f2ba16-20f1-4d4b-84ed-8daca9ca05dd','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:09:03');
INSERT INTO "analysis_runs" VALUES('run_69e7ef12fcbb','680b32f7-dcfb-4fb1-847f-9fed8ddfa6e8','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:09:40');
INSERT INTO "analysis_runs" VALUES('run_68f22a04504f','48f566ce-d59c-4b66-9e03-6da4adada761','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:11:14');
INSERT INTO "analysis_runs" VALUES('run_878314323461','7290729b-69a0-4cde-b518-920f48c847e6','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:12:52');
INSERT INTO "analysis_runs" VALUES('run_87a742a30952','350adb2f-e2bb-4313-a78e-d4469f3fb648','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:14:25');
INSERT INTO "analysis_runs" VALUES('run_4eeee0816fbd','c097816b-bfbf-45ce-9794-c7a74d266b75','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:15:58');
INSERT INTO "analysis_runs" VALUES('run_869c4a8267ae','8d7bbbd7-d789-4609-a093-8385ada90c21','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:17:31');
INSERT INTO "analysis_runs" VALUES('run_12ced9e4d8bf','c9275605-0cf2-45a0-a2cf-77d25c60fa3e','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:19:04');
INSERT INTO "analysis_runs" VALUES('run_69db45712904','6d015c87-6202-4311-80f7-19ab01907317','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:20:38');
INSERT INTO "analysis_runs" VALUES('run_807c40b551b4','88d67924-3888-4e2a-bc09-4894f2ecabf0','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:22:11');
INSERT INTO "analysis_runs" VALUES('run_04a83a11f828','8274683d-6dc8-44ce-9dd7-3de38f4835a3','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:25:18');
INSERT INTO "analysis_runs" VALUES('run_207f60eed915','d1ee1b4f-9d2d-41d6-827a-37f924087adf','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:26:51');
INSERT INTO "analysis_runs" VALUES('run_d739f0f6862b','97279f9f-1e78-48b5-a45f-900c1b30bc3a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:31:03');
INSERT INTO "analysis_runs" VALUES('run_da778f37781c','e962b6d0-10b0-43dc-8d46-98e3a148f3c2','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:32:18');
INSERT INTO "analysis_runs" VALUES('run_78cbb03e3434','857e7523-3519-4ddd-93ee-5ad2b09c35aa','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:33:51');
INSERT INTO "analysis_runs" VALUES('run_bbf4c0cab757','4df64d36-5a44-4faa-b3b6-e0cbd6cdb0ed','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:34:29');
INSERT INTO "analysis_runs" VALUES('run_2302432c2308','98a3ac9e-a382-423f-8397-5272260408b7','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:36:12');
INSERT INTO "analysis_runs" VALUES('run_a0d73aef55c8','651e01ae-7259-4c03-b66f-431fab81511a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:36:35');
INSERT INTO "analysis_runs" VALUES('run_12eede140cbe','4361dd96-b821-4cc2-9564-ab885fd85649','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:37:24');
INSERT INTO "analysis_runs" VALUES('run_35cff4c91968','0575c83d-ff1b-492b-8ef0-66c0e35fca24','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 07:38:57');
INSERT INTO "analysis_runs" VALUES('run_63a30193c76a','5237a724-4eca-4d68-8644-79217076c979','companies/{code}/comparisons','["002064.SZ", "002092.SZ", "002258.SZ"]','2026Q2','parent_company','failed','2026-08-25 08:10:28');
INSERT INTO "analysis_runs" VALUES('run_c3a1097953d5','978235b7-ef5d-4d71-8486-a6085c529612','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:50:15');
INSERT INTO "analysis_runs" VALUES('run_504dfa171c41','2e6f6ee1-cc5d-45a9-881a-170a026bc375','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:50:20');
INSERT INTO "analysis_runs" VALUES('run_cc19c2cb058b','2c72910b-dc51-4a84-8884-c5e191024fdf','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:51:00');
INSERT INTO "analysis_runs" VALUES('run_8683ab680fdb','22068966-2e6e-44ff-9323-ad75156d3432','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:51:15');
INSERT INTO "analysis_runs" VALUES('run_8fd17a9ddb52','a02fd8a7-0aa3-4911-aa98-e6e39857a0e3','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:51:40');
INSERT INTO "analysis_runs" VALUES('run_e9d990a03e42','d2e65b9f-1d00-496b-92ef-94bd2c500e43','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:51:57');
INSERT INTO "analysis_runs" VALUES('run_4a480fd3f184','d7447884-059c-4ae5-9234-f3f4a46548cb','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 08:52:41');
INSERT INTO "analysis_runs" VALUES('run_3a77f6e3d6ab','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','companies/{code}/events','["600518.SH"]','2016-09-15','parent_company','completed','2026-08-25 08:54:01');
INSERT INTO "analysis_runs" VALUES('run_c90ef18e8e02','0a9b20a1-2490-4922-b59b-e5f50bd1a5a3','companies/{code}/events','["600518.SH"]','2016-09-15','parent_company','completed','2026-08-25 08:55:06');
INSERT INTO "analysis_runs" VALUES('run_89bceeafc7e1','3511127b-972e-4b59-82c7-32494d8e3191','companies/{code}/events','["600518.SH"]','2016-09-15','parent_company','completed','2026-08-25 08:55:20');
INSERT INTO "analysis_runs" VALUES('run_2a72e17b10b8','10be80db-2c1c-47de-a2ae-7c34da43e2ac','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:29:27');
INSERT INTO "analysis_runs" VALUES('run_ee608c0c84e2','36a76385-e1f8-4eba-ad3f-ef1da288903e','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:29:28');
INSERT INTO "analysis_runs" VALUES('run_b2ec8319ee22','3a1e518d-f593-43f1-aac0-5b1a66ed451f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:30:40');
INSERT INTO "analysis_runs" VALUES('run_587d30b4d5e4','58986d6a-5da6-4701-94ec-594a313ba281','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:30:40');
INSERT INTO "analysis_runs" VALUES('run_f277303c14a8','1734a03c-63da-44bc-b9dc-f90fdd79ee68','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:31:24');
INSERT INTO "analysis_runs" VALUES('run_5b08e993c759','33c4daa3-84cf-4d70-84ad-0f7bd6a85994','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:31:24');
INSERT INTO "analysis_runs" VALUES('run_2181c1cb5b9d','5ae574a8-901d-47f9-ba99-eb856a6eb4ba','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:31:26');
INSERT INTO "analysis_runs" VALUES('run_836841d63a4e','de50bf1a-1c05-45a8-881c-1744556a232c','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:31:26');
INSERT INTO "analysis_runs" VALUES('run_5e94a3b8ba5a','f74c4d1b-1487-483b-9a6e-cdc032ea6455','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:31:27');
INSERT INTO "analysis_runs" VALUES('run_b9d3e90f6861','e6381f06-9408-4d01-aa8f-9aaa7b1bad7c','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:31:27');
INSERT INTO "analysis_runs" VALUES('run_818a0cb8f5b7','b93de4ee-a850-4c8d-80c1-934cf1193eef','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:31:34');
INSERT INTO "analysis_runs" VALUES('run_1fc176739ac0','3d637c26-38a7-46f5-82b8-5e6960760e5d','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:31:34');
INSERT INTO "analysis_runs" VALUES('run_d57c5010ea62','ca5efde3-966f-4799-8f2c-ea9a9a77967a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:32:58');
INSERT INTO "analysis_runs" VALUES('run_e9bc5a492eef','12a26175-616f-44a3-aa6b-bd83b1c13012','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:32:58');
INSERT INTO "analysis_runs" VALUES('run_d685a2f74ed4','71ed0758-093a-446d-aab2-f4cb28430845','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:33:09');
INSERT INTO "analysis_runs" VALUES('run_d789b8b54c95','6c523052-3c10-4dbf-a719-24175484f25b','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:33:09');
INSERT INTO "analysis_runs" VALUES('run_083e07bf38b2','05f08b1a-8261-47c6-868b-ba61c11dcb4e','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:34:31');
INSERT INTO "analysis_runs" VALUES('run_c44f02bbbfe5','7cbf9495-70cd-4f2d-a6e4-039edd54f76c','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:34:31');
INSERT INTO "analysis_runs" VALUES('run_0d952152db4a','3696af77-2fd9-4654-b3c8-2ccaeecc85f0','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:34:42');
INSERT INTO "analysis_runs" VALUES('run_b1be797f3efb','c749f3b4-6f97-44ad-9aea-bdbec1e35e3f','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:34:42');
INSERT INTO "analysis_runs" VALUES('run_853b4888aefa','33e0dc83-0b5f-4d26-abc1-5198a12150be','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:36:05');
INSERT INTO "analysis_runs" VALUES('run_e1bb04b6f287','58d4a0ef-bf89-4b81-9e35-4009ef51e725','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:36:05');
INSERT INTO "analysis_runs" VALUES('run_86deeaae56e6','96417a07-93f9-49db-a4aa-fa6ea457e1ce','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:36:15');
INSERT INTO "analysis_runs" VALUES('run_1ba9c5038c09','3c95f90a-3e27-421b-aa9b-baced16dcac2','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:36:15');
INSERT INTO "analysis_runs" VALUES('run_c3f28ce86cdb','4dad10ad-a0d0-4135-a865-f516ef0c2f2c','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:37:21');
INSERT INTO "analysis_runs" VALUES('run_2a51befebc69','0290fc7c-1409-47cc-98aa-a4608b15680c','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:37:27');
INSERT INTO "analysis_runs" VALUES('run_4ec68169c1aa','5fc13864-b81e-4366-bb37-cafdf46b18b9','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:37:32');
INSERT INTO "analysis_runs" VALUES('run_96dfdf641856','5722c359-c455-4332-95e9-197643a6bac4','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:37:38');
INSERT INTO "analysis_runs" VALUES('run_38cb1c4b4a60','8b2ecdad-0fe8-46bc-85ba-0502adfbc1d8','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:37:38');
INSERT INTO "analysis_runs" VALUES('run_eb2fa20a7f18','75f79c87-5279-42e1-8443-6512ec9ce7c9','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:37:48');
INSERT INTO "analysis_runs" VALUES('run_d12fb95a4833','29b4e5c5-8419-49af-87e8-13aa3d0c2d09','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:37:48');
INSERT INTO "analysis_runs" VALUES('run_120a78d0fe24','2404500c-55fb-46ef-83ed-513e2895068d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:39:11');
INSERT INTO "analysis_runs" VALUES('run_ff294c83d2c4','2ef01e00-7583-4966-b6a7-7ed9bbd64fa4','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:39:11');
INSERT INTO "analysis_runs" VALUES('run_139452c4d5ac','6647dba4-8b7e-440e-b24d-f2526daea4fe','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:39:21');
INSERT INTO "analysis_runs" VALUES('run_93e983d51d73','987e8c20-7d5e-4cb6-b308-dafb06087f5c','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:39:21');
INSERT INTO "analysis_runs" VALUES('run_2c4f3c59880c','d21a6c96-da64-491f-9fbe-1750cc98e3f5','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:39:53');
INSERT INTO "analysis_runs" VALUES('run_8805f6ed8116','68404c9b-6ee7-492e-a8c4-edecb365ea62','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:39:53');
INSERT INTO "analysis_runs" VALUES('run_2599e5b28588','b2f4f5f0-0946-40ed-8aaa-cfbd627e0fb0','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:41:28');
INSERT INTO "analysis_runs" VALUES('run_4f527973009f','46ce48ff-1d2e-4b73-a9b8-152911b03c0b','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:41:28');
INSERT INTO "analysis_runs" VALUES('run_72c8ce6a7238','7cb15ab5-80f8-4f5c-9b4e-aed8aaa52c27','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:43:00');
INSERT INTO "analysis_runs" VALUES('run_d2d8a3fdc3b1','78159339-9ef1-4000-8744-d1c63b74f5e0','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:43:00');
INSERT INTO "analysis_runs" VALUES('run_f8601663ed0d','dbc5cdf9-0fb1-4f29-bf03-99592d8e048a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:44:33');
INSERT INTO "analysis_runs" VALUES('run_5915a9fff8bb','0f8dfc75-4263-4563-992d-7dd91c49a286','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:44:33');
INSERT INTO "analysis_runs" VALUES('run_63794e796348','dae56990-4fc5-4b43-98a0-c8194ddf1640','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:46:06');
INSERT INTO "analysis_runs" VALUES('run_0b652324edaf','d6dbebf3-7904-4621-9d00-264dde7da032','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:46:06');
INSERT INTO "analysis_runs" VALUES('run_c7323b0f5af8','17fc6932-416c-4363-9a10-8859436688dc','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:47:42');
INSERT INTO "analysis_runs" VALUES('run_f57145a15784','40e9a3b8-a87a-4b1f-aedd-7e0ad78bb5ec','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:47:42');
INSERT INTO "analysis_runs" VALUES('run_f573fc744cd9','8b8fb8b8-a10e-4e2f-9ed5-8f9d25b2bbd6','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:49:17');
INSERT INTO "analysis_runs" VALUES('run_02c68c3fabd3','168d158a-2b07-4070-90e8-fc0d4166031f','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:49:17');
INSERT INTO "analysis_runs" VALUES('run_c6d5559b8870','431696f9-44f9-4662-bfe6-91aa7365e3f3','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:50:39');
INSERT INTO "analysis_runs" VALUES('run_f460a47defc4','3d1ddb41-e858-4c6d-80b1-07d87b87538b','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:50:39');
INSERT INTO "analysis_runs" VALUES('run_ad9ded0fada9','242a48c8-40c7-4521-9c38-70500fb595a9','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:52:12');
INSERT INTO "analysis_runs" VALUES('run_0d9d4d2b4ca1','4e9fb5ab-cb50-4a98-9e7a-625e0dd6be59','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:52:13');
INSERT INTO "analysis_runs" VALUES('run_a0f03c3b0d37','b7e7066d-87c1-4bba-affe-32c1d814ba6e','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:53:45');
INSERT INTO "analysis_runs" VALUES('run_38dfc9c45621','a8b96ff4-21bc-4d1b-975d-d19a8c2faf88','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:53:45');
INSERT INTO "analysis_runs" VALUES('run_63fe612c8d58','2735a5eb-f4f3-4ab3-ab87-948be2c82d4c','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:55:19');
INSERT INTO "analysis_runs" VALUES('run_a775732e4d3e','f3689294-d9e2-406a-8419-08c41f3fa1d5','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:55:19');
INSERT INTO "analysis_runs" VALUES('run_8a56b8018ee8','5db78998-edf5-489b-bda5-2fe50032086c','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:56:52');
INSERT INTO "analysis_runs" VALUES('run_4486de33b21c','01d028eb-fa35-4534-9073-abf5dd61150f','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:56:52');
INSERT INTO "analysis_runs" VALUES('run_ff24253bf51a','2cae3334-2256-4cca-a731-5aac976f8cc0','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:58:25');
INSERT INTO "analysis_runs" VALUES('run_9a8f4f75546b','cb80b6b3-eb31-4a3a-bdee-054cddffefc8','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:58:25');
INSERT INTO "analysis_runs" VALUES('run_7ae08f23bf52','d4eb8907-7e7f-4ef3-9377-f02feab53137','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 09:59:59');
INSERT INTO "analysis_runs" VALUES('run_9b5ab77a1c59','8255a9b3-0118-44d3-8957-9ee6f809802e','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 09:59:59');
INSERT INTO "analysis_runs" VALUES('run_79a515d419cf','1b3159d1-ece0-4f78-86fc-20188a5b8955','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:01:11');
INSERT INTO "analysis_runs" VALUES('run_5f514705e468','f70ec18d-b89d-4fe9-96de-19771110193a','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:01:11');
INSERT INTO "analysis_runs" VALUES('run_372e738f04bf','0c6de9f5-72f3-493f-a7b1-e05ec1532d65','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:02:44');
INSERT INTO "analysis_runs" VALUES('run_88f3e01a4472','0b3c14b6-0868-4b59-9b52-5baadde0e2be','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:02:44');
INSERT INTO "analysis_runs" VALUES('run_87cf44513ee1','0d9142b5-a062-4268-86cb-762585bebe91','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:04:17');
INSERT INTO "analysis_runs" VALUES('run_c01615b464ee','dc825631-991c-47c5-beeb-7fd4b113580b','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:04:17');
INSERT INTO "analysis_runs" VALUES('run_4508c8d89e53','966e430e-5d64-4439-ae2e-ebb7947410b7','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:06:21');
INSERT INTO "analysis_runs" VALUES('run_8d8b370b8d22','d318bb04-a6c9-443d-8c35-eab18b6c1afd','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:06:21');
INSERT INTO "analysis_runs" VALUES('run_0df8c8fba6ed','aa230743-eb8f-458f-b907-55e0ff405cd4','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:06:24');
INSERT INTO "analysis_runs" VALUES('run_e276f32fe62b','ea019bf4-ce7c-4f83-8869-bf85a5b3f77f','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:06:24');
INSERT INTO "analysis_runs" VALUES('run_98767a41eba8','d36d3624-b0e6-44b3-b527-6a284a37644a','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:06:26');
INSERT INTO "analysis_runs" VALUES('run_ecd9747b58d4','2e9e288d-676d-48ff-bb7a-86263cb6efb2','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:06:26');
INSERT INTO "analysis_runs" VALUES('run_27a46b30f4f7','040a8293-0f2b-443e-99dc-49dde3f07894','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:07:54');
INSERT INTO "analysis_runs" VALUES('run_f474ddb1661d','ed9a8bbc-c8e6-4a01-a19e-70213f599ab0','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:07:54');
INSERT INTO "analysis_runs" VALUES('run_f6217412ba5f','351be3ae-d864-4ca9-8311-10885d1b26e4','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:03');
INSERT INTO "analysis_runs" VALUES('run_e75ede61c9cc','bdf2a2d1-60c1-471d-83d3-59adac4dfc19','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:03');
INSERT INTO "analysis_runs" VALUES('run_495bb62d0372','983413fb-b275-4bb8-a028-49fb09fdc72f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:04');
INSERT INTO "analysis_runs" VALUES('run_546630e9a2bd','90bfbef1-73e7-43b5-ac80-74e948151736','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:04');
INSERT INTO "analysis_runs" VALUES('run_e3821572f39b','9bb69d2a-a73e-4fcb-8c79-b64c6c104151','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:05');
INSERT INTO "analysis_runs" VALUES('run_d2cec7a9c7c5','9dbc200b-31e3-4828-8663-64ababc4883d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:05');
INSERT INTO "analysis_runs" VALUES('run_0625f725ac1c','b2cd4b59-34ca-4e9c-ad95-52b73eb6503f','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:06');
INSERT INTO "analysis_runs" VALUES('run_f16e62eccaff','2e5bf19e-99cd-4929-9239-f8af4af25db6','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:06');
INSERT INTO "analysis_runs" VALUES('run_237bc98dcd7c','3ec47006-a493-446c-925f-48b8c50e00da','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:07');
INSERT INTO "analysis_runs" VALUES('run_0c49f159b23c','bc78e57b-b672-449d-a881-1bc615acecd5','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:07');
INSERT INTO "analysis_runs" VALUES('run_d8f9871c093b','5a517fae-d1d0-4f57-acab-12567b2c172c','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:08');
INSERT INTO "analysis_runs" VALUES('run_76f8c4691cd2','7e053726-bb2e-42ed-b513-1b0d44f4bbd3','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:08');
INSERT INTO "analysis_runs" VALUES('run_9b6961e714c6','c9757573-9da3-4e25-b949-43b27871813b','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:09');
INSERT INTO "analysis_runs" VALUES('run_fd734568a34d','8d253761-be55-4e02-bada-2e72c45a75ab','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:09');
INSERT INTO "analysis_runs" VALUES('run_e879ff7808ad','042bdeb5-b568-4923-9395-9d1fab1c4f66','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:10');
INSERT INTO "analysis_runs" VALUES('run_708f685ba047','18cc96da-0307-4518-b574-f9134e929e31','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:10');
INSERT INTO "analysis_runs" VALUES('run_f1f51cf1b413','4d788877-7e4e-4f54-b32d-d84d101555d2','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:11');
INSERT INTO "analysis_runs" VALUES('run_afcdc108d737','0896e582-423e-4879-b51e-af73d855aafa','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:11');
INSERT INTO "analysis_runs" VALUES('run_5c76244f806d','cd5ca9ea-e605-4975-adee-6e8c8ffcf391','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:08:12');
INSERT INTO "analysis_runs" VALUES('run_b9f1bca20a6a','b242ecc7-6c53-4c28-97c8-5d05325f973a','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:08:12');
INSERT INTO "analysis_runs" VALUES('run_361de6ef89c0','e8f1a059-087e-46bf-9276-8e179752069d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:13:16');
INSERT INTO "analysis_runs" VALUES('run_4626bda3ea8c','d9c73734-fa97-498a-8da6-67139310bd1a','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:13:16');
INSERT INTO "analysis_runs" VALUES('run_f0eb332651ed','c391421a-1f50-4e24-a4da-a8814986492d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:13:18');
INSERT INTO "analysis_runs" VALUES('run_442c0da939c3','ca9fcc3f-7799-469a-bc89-745c359bef27','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:13:18');
INSERT INTO "analysis_runs" VALUES('run_923e9132ab4d','d863d5bd-4a28-4c0e-b141-e6daa6c2d853','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:14:49');
INSERT INTO "analysis_runs" VALUES('run_b1c25f755245','88799bff-6729-48e2-9621-5efa441427b3','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:14:49');
INSERT INTO "analysis_runs" VALUES('run_be3a1f8917bf','93e64734-cd1d-4ea2-a78b-b4cb730cda61','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:16:24');
INSERT INTO "analysis_runs" VALUES('run_4324f1c03390','2dd59523-b109-441b-82fb-27d82cfef40e','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:16:24');
INSERT INTO "analysis_runs" VALUES('run_ba5763336d14','39f4ca6a-df89-4219-b3cb-530af3e17420','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:17:13');
INSERT INTO "analysis_runs" VALUES('run_edc0ab9bc593','3ea4dc7f-ec89-45eb-8fd8-39f8d84293a3','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:17:13');
INSERT INTO "analysis_runs" VALUES('run_0e14d947f731','95bb1653-f8ba-478d-a2e3-1a2627a4ebf1','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:17:30');
INSERT INTO "analysis_runs" VALUES('run_ac710bdce646','2cac4476-8106-42d7-aba9-3704c9118f78','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:17:30');
INSERT INTO "analysis_runs" VALUES('run_1d3e8cd4d318','e39be5d6-aa4c-412e-90b5-2b865c51ef62','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:17:37');
INSERT INTO "analysis_runs" VALUES('run_e31a0e9ec8c4','d42576f0-80d9-422c-8eb3-111e846183d1','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:17:37');
INSERT INTO "analysis_runs" VALUES('run_f2a6b9c24d46','435bd4f6-f9a4-4201-8f5f-64d0050f5b3e','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:18:48');
INSERT INTO "analysis_runs" VALUES('run_cede69dff71c','8c6e81e1-ed56-4e24-a696-344352ebdac8','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:18:48');
INSERT INTO "analysis_runs" VALUES('run_f76b7ccef063','b06d23c2-bcb3-4a53-8ed8-364ae0ed05b3','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:20:21');
INSERT INTO "analysis_runs" VALUES('run_d5ae91c1a496','c363296c-ac46-418b-80c2-04b96ca8afbb','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:20:21');
INSERT INTO "analysis_runs" VALUES('run_af8a6ad0f769','eb9ebe93-e2a3-41b0-bb9f-fc0fd49bd868','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:21:55');
INSERT INTO "analysis_runs" VALUES('run_1a183d28f900','deb37603-1a87-41b7-8834-bd7a773253db','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:21:55');
INSERT INTO "analysis_runs" VALUES('run_3315ed4be3c1','76ac4206-6852-441e-b341-9ac2ff02696d','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:23:28');
INSERT INTO "analysis_runs" VALUES('run_11a26727b9e5','40bddaf0-f395-492e-8000-9bf31ac2d7d4','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:23:28');
INSERT INTO "analysis_runs" VALUES('run_28c33e80a727','d103a245-d200-4ded-98ca-694781310cac','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:25:01');
INSERT INTO "analysis_runs" VALUES('run_31fe8563ddc7','becc1157-ed37-432f-a592-69a677a6869b','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:25:01');
INSERT INTO "analysis_runs" VALUES('run_3bfc696a5bb8','0f843671-fe51-4a21-b283-a1d2a4e65897','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:26:36');
INSERT INTO "analysis_runs" VALUES('run_0465eb117a43','d97d9c67-c4f7-4ae7-bead-6c7b7a60a2f2','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:26:36');
INSERT INTO "analysis_runs" VALUES('run_286753c5ef5c','f6f63b1b-a141-489e-856e-39fc70702e76','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:29:22');
INSERT INTO "analysis_runs" VALUES('run_362e1cdd0a81','9dacbc6d-c16e-4773-b557-edcaf7b4ea1f','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:29:22');
INSERT INTO "analysis_runs" VALUES('run_6f58c32aeda5','7ffbfd13-4dc7-4d97-877f-88b0a850bc98','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:29:23');
INSERT INTO "analysis_runs" VALUES('run_b256cb0a3e56','55bdd22c-0532-40d1-94dd-f57bba1110a7','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:29:23');
INSERT INTO "analysis_runs" VALUES('run_a1f82483df24','fd1d89e4-2d78-4b01-98d5-8d3697601222','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:30:55');
INSERT INTO "analysis_runs" VALUES('run_312e4f1afa87','90947a95-352a-446f-9557-a63f5a8dc443','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:30:55');
INSERT INTO "analysis_runs" VALUES('run_312f79a768c0','c373fe6e-1123-4b2c-8187-1307b064f0c3','companies/{code}/events','["600518.SH"]','2023-09-10','parent_company','completed','2026-08-25 10:32:28');
INSERT INTO "analysis_runs" VALUES('run_1c42e72889de','9ec2ddfb-2f6b-471d-acc5-495a90dc93f4','companies/{code}/finance','["600518.SH"]','20181231','parent_company','completed','2026-08-25 10:32:28');
CREATE TABLE announcements (
	object_id VARCHAR(128) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	ann_dt VARCHAR(10), 
	n_info_title VARCHAR(512) NOT NULL, 
	n_info_fcode VARCHAR(64), 
	sentiment VARCHAR(16), 
	sentiment_method VARCHAR(32), 
	source_uri VARCHAR(1024), 
	content_hash VARCHAR(128), 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	UNIQUE (object_id)
);
INSERT INTO "announcements" VALUES('kmfy_ann_20181229_csrc','600518.SH','2018-12-29','康美药业股份有限公司关于收到中国证券监督管理委员会立案调查通知的公告','010305','negative','manual_fixture','http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1205599888',NULL,1,'kmfy_ann_20181229_csrc','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.937445','2026-08-25 08:44:45.937446','null',NULL);
INSERT INTO "announcements" VALUES('kmfy_ann_20190430_restate','600518.SH','2019-04-30','康美药业股份有限公司关于前期会计差错更正的公告','010305','negative','manual_fixture','http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1205987654',NULL,2,'kmfy_ann_20190430_restate','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.937513','2026-08-25 08:44:45.937513','null',NULL);
INSERT INTO "announcements" VALUES('kmfy_ann_20190517_st','600518.SH','2019-05-17','康美药业股份有限公司关于公司股票被实施其他风险警示的公告','010305','negative','manual_fixture','http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1206123456',NULL,3,'kmfy_ann_20190517_st','scripts/load_kangmei_fixture.py',3,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.937538','2026-08-25 08:44:45.937538','null',NULL);
INSERT INTO "announcements" VALUES('kmfy_ann_20190816_penalty','600518.SH','2019-08-16','康美药业股份有限公司关于收到中国证监会《行政处罚及市场禁入事先告知书》的公告','010305','negative','manual_fixture','http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600518&announcementId=1206312345',NULL,4,'kmfy_ann_20190816_penalty','scripts/load_kangmei_fixture.py',4,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.937558','2026-08-25 08:44:45.937559','null',NULL);
CREATE TABLE balance_sheet (
	wind_code VARCHAR(32) NOT NULL, 
	report_period VARCHAR(10) NOT NULL, 
	statement_type VARCHAR(32) NOT NULL, 
	ann_dt VARCHAR(10), 
	monetary_cap FLOAT, 
	acct_rcv FLOAT, 
	oth_rcv FLOAT, 
	inventories FLOAT, 
	tot_cur_assets FLOAT, 
	fix_assets FLOAT, 
	goodwill FLOAT, 
	tot_assets FLOAT, 
	st_borrow FLOAT, 
	lt_borrow FLOAT, 
	acct_payable FLOAT, 
	tot_cur_liab FLOAT, 
	tot_liab FLOAT, 
	tot_shrhldr_eqy_incl_min_int FLOAT, 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_bs_report UNIQUE (wind_code, report_period, statement_type, ann_dt, revision_no)
);
INSERT INTO "balance_sheet" VALUES('600518.SH','2015-12-31','408006000','2016-04-25',1580000.0,280000.0,18000.0,980000.0,2950000.0,620000.0,35000.0,3810000.0,460000.0,180000.0,240000.0,1380000.0,2050000.0,1760000.0,1,'kmfy_bs_2015-12-31','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.929794','2026-08-25 08:44:45.929796','null',NULL);
INSERT INTO "balance_sheet" VALUES('600518.SH','2016-12-31','408006000','2017-04-28',2730000.0,310000.0,22000.0,1260000.0,4450000.0,780000.0,55000.0,5480000.0,820000.0,240000.0,320000.0,2270000.0,3100000.0,2380000.0,2,'kmfy_bs_2016-12-31','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.929895','2026-08-25 08:44:45.929895','null',NULL);
INSERT INTO "balance_sheet" VALUES('600518.SH','2017-12-31','408006000','2018-04-26',3420000.0,430000.0,38000.0,1570000.0,5640000.0,880000.0,65000.0,6870000.0,1130000.0,350000.0,450000.0,3160000.0,4220000.0,2650000.0,3,'kmfy_bs_2017-12-31','scripts/load_kangmei_fixture.py',3,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.929934','2026-08-25 08:44:45.929934','null',NULL);
INSERT INTO "balance_sheet" VALUES('600518.SH','2018-12-31','408006000','2019-04-30',180000.0,380000.0,22000.0,920000.0,1620000.0,830000.0,0.0,2650000.0,1350000.0,420000.0,510000.0,3480000.0,4680000.0,-2030000.0,4,'kmfy_bs_2018-12-31','scripts/load_kangmei_fixture.py',4,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.929962','2026-08-25 08:44:45.929963','null',NULL);
CREATE TABLE cash_flow (
	wind_code VARCHAR(32) NOT NULL, 
	report_period VARCHAR(10) NOT NULL, 
	statement_type VARCHAR(32) NOT NULL, 
	ann_dt VARCHAR(10), 
	net_cash_flows_oper_act FLOAT, 
	net_cash_flows_inv_act FLOAT, 
	net_cash_flows_fnc_act FLOAT, 
	net_incr_cash_cash_equ FLOAT, 
	free_cash_flow FLOAT, 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_cf_report UNIQUE (wind_code, report_period, statement_type, ann_dt, revision_no)
);
INSERT INTO "cash_flow" VALUES('600518.SH','2015-12-31','408006000','2016-04-25',42000.0,-185000.0,220000.0,77000.0,-143000.0,1,'kmfy_cf_2015-12-31','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.934498','2026-08-25 08:44:45.934499','null',NULL);
INSERT INTO "cash_flow" VALUES('600518.SH','2016-12-31','408006000','2017-04-28',38000.0,-210000.0,280000.0,108000.0,-172000.0,2,'kmfy_cf_2016-12-31','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.934569','2026-08-25 08:44:45.934569','null',NULL);
INSERT INTO "cash_flow" VALUES('600518.SH','2017-12-31','408006000','2018-04-26',-185000.0,-245000.0,320000.0,-110000.0,-430000.0,3,'kmfy_cf_2017-12-31','scripts/load_kangmei_fixture.py',3,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.934615','2026-08-25 08:44:45.934616','null',NULL);
INSERT INTO "cash_flow" VALUES('600518.SH','2018-12-31','408006000','2019-04-30',-320000.0,-95000.0,150000.0,-265000.0,-415000.0,4,'kmfy_cf_2018-12-31','scripts/load_kangmei_fixture.py',4,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.934639','2026-08-25 08:44:45.934639','null',NULL);
CREATE TABLE claim_evidence_links (
	id INTEGER NOT NULL, 
	claim_id VARCHAR(64) NOT NULL, 
	evidence_id VARCHAR(64) NOT NULL, 
	relation_type VARCHAR(16) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_claim_evidence_link UNIQUE (claim_id, evidence_id, relation_type), 
	FOREIGN KEY(claim_id) REFERENCES claims (claim_id) ON DELETE CASCADE, 
	FOREIGN KEY(evidence_id) REFERENCES evidence_refs (evidence_id) ON DELETE CASCADE
);
INSERT INTO "claim_evidence_links" VALUES(1,'clm_ce29e78b61145097','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(2,'clm_ce29e78b61145097','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(3,'clm_ce29e78b61145097','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(4,'clm_ce29e78b61145097','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(5,'clm_ce29e78b61145097','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(6,'clm_ce29e78b61145097','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(7,'clm_ce29e78b61145097','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(8,'clm_ce29e78b61145097','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(9,'clm_ce29e78b61145097','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(10,'clm_ce29e78b61145097','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(11,'clm_ce29e78b61145097','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(12,'clm_ce29e78b61145097','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(13,'clm_ce29e78b61145097','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(14,'clm_ce29e78b61145097','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(15,'clm_ce29e78b61145097','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(16,'clm_ce29e78b61145097','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(17,'clm_ce29e78b61145097','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(18,'clm_ce29e78b61145097','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(19,'clm_ce29e78b61145097','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(20,'clm_ce29e78b61145097','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:49:11');
INSERT INTO "claim_evidence_links" VALUES(21,'clm_312cf5857b319f60','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(22,'clm_312cf5857b319f60','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(23,'clm_312cf5857b319f60','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(24,'clm_312cf5857b319f60','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(25,'clm_312cf5857b319f60','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(26,'clm_312cf5857b319f60','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(27,'clm_312cf5857b319f60','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(28,'clm_312cf5857b319f60','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(29,'clm_312cf5857b319f60','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(30,'clm_312cf5857b319f60','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(31,'clm_312cf5857b319f60','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(32,'clm_312cf5857b319f60','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(33,'clm_312cf5857b319f60','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(34,'clm_312cf5857b319f60','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(35,'clm_312cf5857b319f60','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(36,'clm_312cf5857b319f60','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(37,'clm_312cf5857b319f60','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(38,'clm_312cf5857b319f60','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(39,'clm_312cf5857b319f60','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(40,'clm_312cf5857b319f60','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:50:59');
INSERT INTO "claim_evidence_links" VALUES(41,'clm_5203faf1a460d67d','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(42,'clm_5203faf1a460d67d','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(43,'clm_5203faf1a460d67d','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(44,'clm_5203faf1a460d67d','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(45,'clm_5203faf1a460d67d','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(46,'clm_5203faf1a460d67d','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(47,'clm_5203faf1a460d67d','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(48,'clm_5203faf1a460d67d','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(49,'clm_5203faf1a460d67d','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(50,'clm_5203faf1a460d67d','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(51,'clm_5203faf1a460d67d','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(52,'clm_5203faf1a460d67d','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(53,'clm_5203faf1a460d67d','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(54,'clm_5203faf1a460d67d','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(55,'clm_5203faf1a460d67d','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(56,'clm_5203faf1a460d67d','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(57,'clm_5203faf1a460d67d','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(58,'clm_5203faf1a460d67d','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(59,'clm_5203faf1a460d67d','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(60,'clm_5203faf1a460d67d','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:52:12');
INSERT INTO "claim_evidence_links" VALUES(61,'clm_5e7dd9547af6b615','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(62,'clm_5e7dd9547af6b615','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(63,'clm_5e7dd9547af6b615','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(64,'clm_5e7dd9547af6b615','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(65,'clm_5e7dd9547af6b615','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(66,'clm_5e7dd9547af6b615','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(67,'clm_5e7dd9547af6b615','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(68,'clm_5e7dd9547af6b615','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(69,'clm_5e7dd9547af6b615','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(70,'clm_5e7dd9547af6b615','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(71,'clm_5e7dd9547af6b615','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(72,'clm_5e7dd9547af6b615','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(73,'clm_5e7dd9547af6b615','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(74,'clm_5e7dd9547af6b615','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(75,'clm_5e7dd9547af6b615','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(76,'clm_5e7dd9547af6b615','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(77,'clm_5e7dd9547af6b615','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(78,'clm_5e7dd9547af6b615','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(79,'clm_5e7dd9547af6b615','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(80,'clm_5e7dd9547af6b615','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:53:46');
INSERT INTO "claim_evidence_links" VALUES(81,'clm_73a0fccd9a2344b3','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(82,'clm_73a0fccd9a2344b3','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(83,'clm_73a0fccd9a2344b3','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(84,'clm_73a0fccd9a2344b3','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(85,'clm_73a0fccd9a2344b3','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(86,'clm_73a0fccd9a2344b3','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(87,'clm_73a0fccd9a2344b3','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(88,'clm_73a0fccd9a2344b3','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(89,'clm_73a0fccd9a2344b3','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(90,'clm_73a0fccd9a2344b3','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(91,'clm_73a0fccd9a2344b3','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(92,'clm_73a0fccd9a2344b3','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(93,'clm_73a0fccd9a2344b3','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(94,'clm_73a0fccd9a2344b3','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(95,'clm_73a0fccd9a2344b3','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(96,'clm_73a0fccd9a2344b3','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(97,'clm_73a0fccd9a2344b3','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(98,'clm_73a0fccd9a2344b3','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(99,'clm_73a0fccd9a2344b3','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(100,'clm_73a0fccd9a2344b3','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:55:19');
INSERT INTO "claim_evidence_links" VALUES(101,'clm_496dd22e7b3f2642','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(102,'clm_496dd22e7b3f2642','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(103,'clm_496dd22e7b3f2642','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(104,'clm_496dd22e7b3f2642','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(105,'clm_496dd22e7b3f2642','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(106,'clm_496dd22e7b3f2642','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(107,'clm_496dd22e7b3f2642','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(108,'clm_496dd22e7b3f2642','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(109,'clm_496dd22e7b3f2642','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(110,'clm_496dd22e7b3f2642','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(111,'clm_496dd22e7b3f2642','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(112,'clm_496dd22e7b3f2642','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(113,'clm_496dd22e7b3f2642','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(114,'clm_496dd22e7b3f2642','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(115,'clm_496dd22e7b3f2642','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(116,'clm_496dd22e7b3f2642','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(117,'clm_496dd22e7b3f2642','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(118,'clm_496dd22e7b3f2642','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(119,'clm_496dd22e7b3f2642','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(120,'clm_496dd22e7b3f2642','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:56:52');
INSERT INTO "claim_evidence_links" VALUES(121,'clm_70c6d21c432c941d','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(122,'clm_70c6d21c432c941d','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(123,'clm_70c6d21c432c941d','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(124,'clm_70c6d21c432c941d','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(125,'clm_70c6d21c432c941d','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(126,'clm_70c6d21c432c941d','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(127,'clm_70c6d21c432c941d','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(128,'clm_70c6d21c432c941d','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(129,'clm_70c6d21c432c941d','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(130,'clm_70c6d21c432c941d','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(131,'clm_70c6d21c432c941d','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(132,'clm_70c6d21c432c941d','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(133,'clm_70c6d21c432c941d','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(134,'clm_70c6d21c432c941d','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(135,'clm_70c6d21c432c941d','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(136,'clm_70c6d21c432c941d','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(137,'clm_70c6d21c432c941d','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(138,'clm_70c6d21c432c941d','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(139,'clm_70c6d21c432c941d','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(140,'clm_70c6d21c432c941d','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:58:25');
INSERT INTO "claim_evidence_links" VALUES(141,'clm_c9bba44592553590','ev_fin_02599521cdbed155','supports',0,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(142,'clm_c9bba44592553590','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(143,'clm_c9bba44592553590','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(144,'clm_c9bba44592553590','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(145,'clm_c9bba44592553590','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(146,'clm_c9bba44592553590','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(147,'clm_c9bba44592553590','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(148,'clm_c9bba44592553590','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(149,'clm_c9bba44592553590','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(150,'clm_c9bba44592553590','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(151,'clm_c9bba44592553590','ev_fin_633671310de9326b','supports',10,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(152,'clm_c9bba44592553590','ev_fin_464910c137146f73','supports',11,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(153,'clm_c9bba44592553590','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(154,'clm_c9bba44592553590','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(155,'clm_c9bba44592553590','ev_fin_336d435f61d20911','supports',14,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(156,'clm_c9bba44592553590','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(157,'clm_c9bba44592553590','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(158,'clm_c9bba44592553590','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(159,'clm_c9bba44592553590','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(160,'clm_c9bba44592553590','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 06:59:58');
INSERT INTO "claim_evidence_links" VALUES(161,'clm_82b7ca7d48ed8d10','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(162,'clm_82b7ca7d48ed8d10','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(163,'clm_82b7ca7d48ed8d10','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(164,'clm_82b7ca7d48ed8d10','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(165,'clm_82b7ca7d48ed8d10','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(166,'clm_82b7ca7d48ed8d10','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(167,'clm_82b7ca7d48ed8d10','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(168,'clm_82b7ca7d48ed8d10','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(169,'clm_82b7ca7d48ed8d10','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(170,'clm_82b7ca7d48ed8d10','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(171,'clm_82b7ca7d48ed8d10','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(172,'clm_82b7ca7d48ed8d10','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(173,'clm_82b7ca7d48ed8d10','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(174,'clm_82b7ca7d48ed8d10','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(175,'clm_82b7ca7d48ed8d10','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(176,'clm_82b7ca7d48ed8d10','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(177,'clm_82b7ca7d48ed8d10','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(178,'clm_82b7ca7d48ed8d10','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(179,'clm_82b7ca7d48ed8d10','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(180,'clm_82b7ca7d48ed8d10','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:01:32');
INSERT INTO "claim_evidence_links" VALUES(181,'clm_92ccbbbd9b24f232','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(182,'clm_92ccbbbd9b24f232','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(183,'clm_92ccbbbd9b24f232','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(184,'clm_92ccbbbd9b24f232','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(185,'clm_92ccbbbd9b24f232','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(186,'clm_92ccbbbd9b24f232','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(187,'clm_92ccbbbd9b24f232','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(188,'clm_92ccbbbd9b24f232','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(189,'clm_92ccbbbd9b24f232','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(190,'clm_92ccbbbd9b24f232','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(191,'clm_92ccbbbd9b24f232','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(192,'clm_92ccbbbd9b24f232','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(193,'clm_92ccbbbd9b24f232','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(194,'clm_92ccbbbd9b24f232','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(195,'clm_92ccbbbd9b24f232','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(196,'clm_92ccbbbd9b24f232','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(197,'clm_92ccbbbd9b24f232','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(198,'clm_92ccbbbd9b24f232','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(199,'clm_92ccbbbd9b24f232','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(200,'clm_92ccbbbd9b24f232','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:03:05');
INSERT INTO "claim_evidence_links" VALUES(201,'clm_4de9f9ae0b05ae9a','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(202,'clm_4de9f9ae0b05ae9a','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(203,'clm_4de9f9ae0b05ae9a','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(204,'clm_4de9f9ae0b05ae9a','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(205,'clm_4de9f9ae0b05ae9a','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(206,'clm_4de9f9ae0b05ae9a','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(207,'clm_4de9f9ae0b05ae9a','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(208,'clm_4de9f9ae0b05ae9a','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(209,'clm_4de9f9ae0b05ae9a','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(210,'clm_4de9f9ae0b05ae9a','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(211,'clm_4de9f9ae0b05ae9a','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(212,'clm_4de9f9ae0b05ae9a','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(213,'clm_4de9f9ae0b05ae9a','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(214,'clm_4de9f9ae0b05ae9a','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(215,'clm_4de9f9ae0b05ae9a','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(216,'clm_4de9f9ae0b05ae9a','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(217,'clm_4de9f9ae0b05ae9a','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(218,'clm_4de9f9ae0b05ae9a','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(219,'clm_4de9f9ae0b05ae9a','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(220,'clm_4de9f9ae0b05ae9a','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:04:33');
INSERT INTO "claim_evidence_links" VALUES(221,'clm_1e53346483557075','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(222,'clm_1e53346483557075','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(223,'clm_1e53346483557075','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(224,'clm_1e53346483557075','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(225,'clm_1e53346483557075','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(226,'clm_1e53346483557075','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(227,'clm_1e53346483557075','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(228,'clm_1e53346483557075','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(229,'clm_1e53346483557075','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(230,'clm_1e53346483557075','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(231,'clm_1e53346483557075','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(232,'clm_1e53346483557075','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(233,'clm_1e53346483557075','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(234,'clm_1e53346483557075','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(235,'clm_1e53346483557075','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(236,'clm_1e53346483557075','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(237,'clm_1e53346483557075','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(238,'clm_1e53346483557075','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(239,'clm_1e53346483557075','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(240,'clm_1e53346483557075','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:04:34');
INSERT INTO "claim_evidence_links" VALUES(241,'clm_c793f4839cb58a97','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(242,'clm_c793f4839cb58a97','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(243,'clm_c793f4839cb58a97','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(244,'clm_c793f4839cb58a97','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(245,'clm_c793f4839cb58a97','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(246,'clm_c793f4839cb58a97','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(247,'clm_c793f4839cb58a97','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(248,'clm_c793f4839cb58a97','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(249,'clm_c793f4839cb58a97','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(250,'clm_c793f4839cb58a97','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(251,'clm_c793f4839cb58a97','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(252,'clm_c793f4839cb58a97','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(253,'clm_c793f4839cb58a97','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(254,'clm_c793f4839cb58a97','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(255,'clm_c793f4839cb58a97','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(256,'clm_c793f4839cb58a97','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(257,'clm_c793f4839cb58a97','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(258,'clm_c793f4839cb58a97','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(259,'clm_c793f4839cb58a97','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(260,'clm_c793f4839cb58a97','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:04:38');
INSERT INTO "claim_evidence_links" VALUES(261,'clm_3e83783bbb448523','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(262,'clm_3e83783bbb448523','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(263,'clm_3e83783bbb448523','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(264,'clm_3e83783bbb448523','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(265,'clm_3e83783bbb448523','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(266,'clm_3e83783bbb448523','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(267,'clm_3e83783bbb448523','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(268,'clm_3e83783bbb448523','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(269,'clm_3e83783bbb448523','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(270,'clm_3e83783bbb448523','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(271,'clm_3e83783bbb448523','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(272,'clm_3e83783bbb448523','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(273,'clm_3e83783bbb448523','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(274,'clm_3e83783bbb448523','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(275,'clm_3e83783bbb448523','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(276,'clm_3e83783bbb448523','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(277,'clm_3e83783bbb448523','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(278,'clm_3e83783bbb448523','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(279,'clm_3e83783bbb448523','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(280,'clm_3e83783bbb448523','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:04:39');
INSERT INTO "claim_evidence_links" VALUES(281,'clm_6d8898c9e6e15763','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(282,'clm_6d8898c9e6e15763','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(283,'clm_6d8898c9e6e15763','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(284,'clm_6d8898c9e6e15763','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(285,'clm_6d8898c9e6e15763','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(286,'clm_6d8898c9e6e15763','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(287,'clm_6d8898c9e6e15763','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(288,'clm_6d8898c9e6e15763','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(289,'clm_6d8898c9e6e15763','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(290,'clm_6d8898c9e6e15763','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(291,'clm_6d8898c9e6e15763','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(292,'clm_6d8898c9e6e15763','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(293,'clm_6d8898c9e6e15763','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(294,'clm_6d8898c9e6e15763','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(295,'clm_6d8898c9e6e15763','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(296,'clm_6d8898c9e6e15763','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(297,'clm_6d8898c9e6e15763','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(298,'clm_6d8898c9e6e15763','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(299,'clm_6d8898c9e6e15763','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(300,'clm_6d8898c9e6e15763','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:04:41');
INSERT INTO "claim_evidence_links" VALUES(301,'clm_a06c9a7a6031b347','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(302,'clm_a06c9a7a6031b347','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(303,'clm_a06c9a7a6031b347','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(304,'clm_a06c9a7a6031b347','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(305,'clm_a06c9a7a6031b347','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(306,'clm_a06c9a7a6031b347','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(307,'clm_a06c9a7a6031b347','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(308,'clm_a06c9a7a6031b347','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(309,'clm_a06c9a7a6031b347','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(310,'clm_a06c9a7a6031b347','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(311,'clm_a06c9a7a6031b347','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(312,'clm_a06c9a7a6031b347','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(313,'clm_a06c9a7a6031b347','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(314,'clm_a06c9a7a6031b347','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(315,'clm_a06c9a7a6031b347','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(316,'clm_a06c9a7a6031b347','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(317,'clm_a06c9a7a6031b347','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(318,'clm_a06c9a7a6031b347','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(319,'clm_a06c9a7a6031b347','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(320,'clm_a06c9a7a6031b347','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:06:12');
INSERT INTO "claim_evidence_links" VALUES(321,'clm_2644daa027b31de8','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(322,'clm_2644daa027b31de8','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(323,'clm_2644daa027b31de8','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(324,'clm_2644daa027b31de8','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(325,'clm_2644daa027b31de8','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(326,'clm_2644daa027b31de8','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(327,'clm_2644daa027b31de8','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(328,'clm_2644daa027b31de8','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(329,'clm_2644daa027b31de8','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(330,'clm_2644daa027b31de8','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(331,'clm_2644daa027b31de8','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(332,'clm_2644daa027b31de8','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(333,'clm_2644daa027b31de8','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(334,'clm_2644daa027b31de8','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(335,'clm_2644daa027b31de8','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(336,'clm_2644daa027b31de8','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(337,'clm_2644daa027b31de8','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(338,'clm_2644daa027b31de8','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(339,'clm_2644daa027b31de8','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(340,'clm_2644daa027b31de8','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:07:23');
INSERT INTO "claim_evidence_links" VALUES(341,'clm_f543045b19087ad7','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(342,'clm_f543045b19087ad7','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(343,'clm_f543045b19087ad7','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(344,'clm_f543045b19087ad7','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(345,'clm_f543045b19087ad7','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(346,'clm_f543045b19087ad7','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(347,'clm_f543045b19087ad7','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(348,'clm_f543045b19087ad7','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(349,'clm_f543045b19087ad7','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(350,'clm_f543045b19087ad7','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(351,'clm_f543045b19087ad7','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(352,'clm_f543045b19087ad7','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(353,'clm_f543045b19087ad7','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(354,'clm_f543045b19087ad7','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(355,'clm_f543045b19087ad7','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(356,'clm_f543045b19087ad7','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(357,'clm_f543045b19087ad7','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(358,'clm_f543045b19087ad7','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(359,'clm_f543045b19087ad7','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(360,'clm_f543045b19087ad7','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:09:03');
INSERT INTO "claim_evidence_links" VALUES(361,'clm_500f2757ecd1fda4','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(362,'clm_500f2757ecd1fda4','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(363,'clm_500f2757ecd1fda4','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(364,'clm_500f2757ecd1fda4','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(365,'clm_500f2757ecd1fda4','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(366,'clm_500f2757ecd1fda4','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(367,'clm_500f2757ecd1fda4','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(368,'clm_500f2757ecd1fda4','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(369,'clm_500f2757ecd1fda4','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(370,'clm_500f2757ecd1fda4','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(371,'clm_500f2757ecd1fda4','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(372,'clm_500f2757ecd1fda4','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(373,'clm_500f2757ecd1fda4','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(374,'clm_500f2757ecd1fda4','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(375,'clm_500f2757ecd1fda4','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(376,'clm_500f2757ecd1fda4','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(377,'clm_500f2757ecd1fda4','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(378,'clm_500f2757ecd1fda4','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(379,'clm_500f2757ecd1fda4','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(380,'clm_500f2757ecd1fda4','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:09:40');
INSERT INTO "claim_evidence_links" VALUES(381,'clm_c6a9dec76bf2d22e','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(382,'clm_c6a9dec76bf2d22e','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(383,'clm_c6a9dec76bf2d22e','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(384,'clm_c6a9dec76bf2d22e','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(385,'clm_c6a9dec76bf2d22e','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(386,'clm_c6a9dec76bf2d22e','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(387,'clm_c6a9dec76bf2d22e','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(388,'clm_c6a9dec76bf2d22e','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(389,'clm_c6a9dec76bf2d22e','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(390,'clm_c6a9dec76bf2d22e','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(391,'clm_c6a9dec76bf2d22e','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(392,'clm_c6a9dec76bf2d22e','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(393,'clm_c6a9dec76bf2d22e','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(394,'clm_c6a9dec76bf2d22e','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(395,'clm_c6a9dec76bf2d22e','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(396,'clm_c6a9dec76bf2d22e','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(397,'clm_c6a9dec76bf2d22e','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(398,'clm_c6a9dec76bf2d22e','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(399,'clm_c6a9dec76bf2d22e','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(400,'clm_c6a9dec76bf2d22e','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:11:14');
INSERT INTO "claim_evidence_links" VALUES(401,'clm_ff99955718e00bf8','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(402,'clm_ff99955718e00bf8','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(403,'clm_ff99955718e00bf8','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(404,'clm_ff99955718e00bf8','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(405,'clm_ff99955718e00bf8','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(406,'clm_ff99955718e00bf8','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(407,'clm_ff99955718e00bf8','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(408,'clm_ff99955718e00bf8','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(409,'clm_ff99955718e00bf8','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(410,'clm_ff99955718e00bf8','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(411,'clm_ff99955718e00bf8','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(412,'clm_ff99955718e00bf8','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(413,'clm_ff99955718e00bf8','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(414,'clm_ff99955718e00bf8','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(415,'clm_ff99955718e00bf8','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(416,'clm_ff99955718e00bf8','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(417,'clm_ff99955718e00bf8','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(418,'clm_ff99955718e00bf8','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(419,'clm_ff99955718e00bf8','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(420,'clm_ff99955718e00bf8','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:12:52');
INSERT INTO "claim_evidence_links" VALUES(421,'clm_6e5b5a2cd5a834f7','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(422,'clm_6e5b5a2cd5a834f7','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(423,'clm_6e5b5a2cd5a834f7','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(424,'clm_6e5b5a2cd5a834f7','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(425,'clm_6e5b5a2cd5a834f7','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(426,'clm_6e5b5a2cd5a834f7','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(427,'clm_6e5b5a2cd5a834f7','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(428,'clm_6e5b5a2cd5a834f7','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(429,'clm_6e5b5a2cd5a834f7','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(430,'clm_6e5b5a2cd5a834f7','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(431,'clm_6e5b5a2cd5a834f7','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(432,'clm_6e5b5a2cd5a834f7','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(433,'clm_6e5b5a2cd5a834f7','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(434,'clm_6e5b5a2cd5a834f7','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(435,'clm_6e5b5a2cd5a834f7','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(436,'clm_6e5b5a2cd5a834f7','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(437,'clm_6e5b5a2cd5a834f7','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(438,'clm_6e5b5a2cd5a834f7','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(439,'clm_6e5b5a2cd5a834f7','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(440,'clm_6e5b5a2cd5a834f7','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:14:25');
INSERT INTO "claim_evidence_links" VALUES(441,'clm_a77c03f6dcf9dc86','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(442,'clm_a77c03f6dcf9dc86','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(443,'clm_a77c03f6dcf9dc86','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(444,'clm_a77c03f6dcf9dc86','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(445,'clm_a77c03f6dcf9dc86','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(446,'clm_a77c03f6dcf9dc86','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(447,'clm_a77c03f6dcf9dc86','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(448,'clm_a77c03f6dcf9dc86','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(449,'clm_a77c03f6dcf9dc86','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(450,'clm_a77c03f6dcf9dc86','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(451,'clm_a77c03f6dcf9dc86','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(452,'clm_a77c03f6dcf9dc86','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(453,'clm_a77c03f6dcf9dc86','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(454,'clm_a77c03f6dcf9dc86','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(455,'clm_a77c03f6dcf9dc86','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(456,'clm_a77c03f6dcf9dc86','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(457,'clm_a77c03f6dcf9dc86','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(458,'clm_a77c03f6dcf9dc86','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(459,'clm_a77c03f6dcf9dc86','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(460,'clm_a77c03f6dcf9dc86','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:15:58');
INSERT INTO "claim_evidence_links" VALUES(461,'clm_103e953fedb1dd8c','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(462,'clm_103e953fedb1dd8c','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(463,'clm_103e953fedb1dd8c','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(464,'clm_103e953fedb1dd8c','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(465,'clm_103e953fedb1dd8c','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(466,'clm_103e953fedb1dd8c','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(467,'clm_103e953fedb1dd8c','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(468,'clm_103e953fedb1dd8c','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(469,'clm_103e953fedb1dd8c','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(470,'clm_103e953fedb1dd8c','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(471,'clm_103e953fedb1dd8c','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(472,'clm_103e953fedb1dd8c','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(473,'clm_103e953fedb1dd8c','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(474,'clm_103e953fedb1dd8c','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(475,'clm_103e953fedb1dd8c','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(476,'clm_103e953fedb1dd8c','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(477,'clm_103e953fedb1dd8c','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(478,'clm_103e953fedb1dd8c','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(479,'clm_103e953fedb1dd8c','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(480,'clm_103e953fedb1dd8c','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:17:31');
INSERT INTO "claim_evidence_links" VALUES(481,'clm_8774625f24d3416f','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(482,'clm_8774625f24d3416f','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(483,'clm_8774625f24d3416f','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(484,'clm_8774625f24d3416f','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(485,'clm_8774625f24d3416f','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(486,'clm_8774625f24d3416f','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(487,'clm_8774625f24d3416f','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(488,'clm_8774625f24d3416f','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(489,'clm_8774625f24d3416f','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(490,'clm_8774625f24d3416f','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(491,'clm_8774625f24d3416f','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(492,'clm_8774625f24d3416f','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(493,'clm_8774625f24d3416f','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(494,'clm_8774625f24d3416f','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(495,'clm_8774625f24d3416f','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(496,'clm_8774625f24d3416f','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(497,'clm_8774625f24d3416f','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(498,'clm_8774625f24d3416f','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(499,'clm_8774625f24d3416f','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(500,'clm_8774625f24d3416f','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:19:04');
INSERT INTO "claim_evidence_links" VALUES(501,'clm_c4c8bae84e288fa1','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(502,'clm_c4c8bae84e288fa1','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(503,'clm_c4c8bae84e288fa1','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(504,'clm_c4c8bae84e288fa1','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(505,'clm_c4c8bae84e288fa1','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(506,'clm_c4c8bae84e288fa1','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(507,'clm_c4c8bae84e288fa1','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(508,'clm_c4c8bae84e288fa1','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(509,'clm_c4c8bae84e288fa1','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(510,'clm_c4c8bae84e288fa1','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(511,'clm_c4c8bae84e288fa1','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(512,'clm_c4c8bae84e288fa1','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(513,'clm_c4c8bae84e288fa1','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(514,'clm_c4c8bae84e288fa1','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(515,'clm_c4c8bae84e288fa1','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(516,'clm_c4c8bae84e288fa1','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(517,'clm_c4c8bae84e288fa1','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(518,'clm_c4c8bae84e288fa1','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(519,'clm_c4c8bae84e288fa1','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(520,'clm_c4c8bae84e288fa1','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:20:38');
INSERT INTO "claim_evidence_links" VALUES(521,'clm_72d2602d31516918','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(522,'clm_72d2602d31516918','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(523,'clm_72d2602d31516918','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(524,'clm_72d2602d31516918','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(525,'clm_72d2602d31516918','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(526,'clm_72d2602d31516918','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(527,'clm_72d2602d31516918','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(528,'clm_72d2602d31516918','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(529,'clm_72d2602d31516918','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(530,'clm_72d2602d31516918','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(531,'clm_72d2602d31516918','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(532,'clm_72d2602d31516918','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(533,'clm_72d2602d31516918','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(534,'clm_72d2602d31516918','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(535,'clm_72d2602d31516918','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(536,'clm_72d2602d31516918','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(537,'clm_72d2602d31516918','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(538,'clm_72d2602d31516918','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(539,'clm_72d2602d31516918','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(540,'clm_72d2602d31516918','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:22:11');
INSERT INTO "claim_evidence_links" VALUES(541,'clm_88b8e547f3f7de81','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(542,'clm_88b8e547f3f7de81','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(543,'clm_88b8e547f3f7de81','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(544,'clm_88b8e547f3f7de81','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(545,'clm_88b8e547f3f7de81','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(546,'clm_88b8e547f3f7de81','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(547,'clm_88b8e547f3f7de81','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(548,'clm_88b8e547f3f7de81','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(549,'clm_88b8e547f3f7de81','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(550,'clm_88b8e547f3f7de81','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(551,'clm_88b8e547f3f7de81','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(552,'clm_88b8e547f3f7de81','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(553,'clm_88b8e547f3f7de81','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(554,'clm_88b8e547f3f7de81','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(555,'clm_88b8e547f3f7de81','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(556,'clm_88b8e547f3f7de81','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(557,'clm_88b8e547f3f7de81','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(558,'clm_88b8e547f3f7de81','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(559,'clm_88b8e547f3f7de81','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(560,'clm_88b8e547f3f7de81','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:25:18');
INSERT INTO "claim_evidence_links" VALUES(561,'clm_b0460fca3c6479fb','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(562,'clm_b0460fca3c6479fb','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(563,'clm_b0460fca3c6479fb','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(564,'clm_b0460fca3c6479fb','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(565,'clm_b0460fca3c6479fb','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(566,'clm_b0460fca3c6479fb','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(567,'clm_b0460fca3c6479fb','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(568,'clm_b0460fca3c6479fb','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(569,'clm_b0460fca3c6479fb','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(570,'clm_b0460fca3c6479fb','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(571,'clm_b0460fca3c6479fb','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(572,'clm_b0460fca3c6479fb','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(573,'clm_b0460fca3c6479fb','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(574,'clm_b0460fca3c6479fb','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(575,'clm_b0460fca3c6479fb','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(576,'clm_b0460fca3c6479fb','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(577,'clm_b0460fca3c6479fb','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(578,'clm_b0460fca3c6479fb','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(579,'clm_b0460fca3c6479fb','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(580,'clm_b0460fca3c6479fb','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:26:51');
INSERT INTO "claim_evidence_links" VALUES(581,'clm_558509067c49622e','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(582,'clm_558509067c49622e','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(583,'clm_558509067c49622e','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(584,'clm_558509067c49622e','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(585,'clm_558509067c49622e','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(586,'clm_558509067c49622e','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(587,'clm_558509067c49622e','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(588,'clm_558509067c49622e','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(589,'clm_558509067c49622e','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(590,'clm_558509067c49622e','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(591,'clm_558509067c49622e','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(592,'clm_558509067c49622e','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(593,'clm_558509067c49622e','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(594,'clm_558509067c49622e','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(595,'clm_558509067c49622e','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(596,'clm_558509067c49622e','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(597,'clm_558509067c49622e','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(598,'clm_558509067c49622e','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(599,'clm_558509067c49622e','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(600,'clm_558509067c49622e','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:31:03');
INSERT INTO "claim_evidence_links" VALUES(601,'clm_728d15106d1b7001','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(602,'clm_728d15106d1b7001','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(603,'clm_728d15106d1b7001','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(604,'clm_728d15106d1b7001','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(605,'clm_728d15106d1b7001','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(606,'clm_728d15106d1b7001','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(607,'clm_728d15106d1b7001','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(608,'clm_728d15106d1b7001','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(609,'clm_728d15106d1b7001','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(610,'clm_728d15106d1b7001','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(611,'clm_728d15106d1b7001','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(612,'clm_728d15106d1b7001','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(613,'clm_728d15106d1b7001','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(614,'clm_728d15106d1b7001','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(615,'clm_728d15106d1b7001','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(616,'clm_728d15106d1b7001','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(617,'clm_728d15106d1b7001','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(618,'clm_728d15106d1b7001','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(619,'clm_728d15106d1b7001','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(620,'clm_728d15106d1b7001','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:32:18');
INSERT INTO "claim_evidence_links" VALUES(621,'clm_2b0d4fadee94681b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(622,'clm_2b0d4fadee94681b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(623,'clm_2b0d4fadee94681b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(624,'clm_2b0d4fadee94681b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(625,'clm_2b0d4fadee94681b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(626,'clm_2b0d4fadee94681b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(627,'clm_2b0d4fadee94681b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(628,'clm_2b0d4fadee94681b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(629,'clm_2b0d4fadee94681b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(630,'clm_2b0d4fadee94681b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(631,'clm_2b0d4fadee94681b','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(632,'clm_2b0d4fadee94681b','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(633,'clm_2b0d4fadee94681b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(634,'clm_2b0d4fadee94681b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(635,'clm_2b0d4fadee94681b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(636,'clm_2b0d4fadee94681b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(637,'clm_2b0d4fadee94681b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(638,'clm_2b0d4fadee94681b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(639,'clm_2b0d4fadee94681b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(640,'clm_2b0d4fadee94681b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:33:51');
INSERT INTO "claim_evidence_links" VALUES(641,'clm_ee606d3716588b44','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(642,'clm_ee606d3716588b44','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(643,'clm_ee606d3716588b44','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(644,'clm_ee606d3716588b44','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(645,'clm_ee606d3716588b44','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(646,'clm_ee606d3716588b44','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(647,'clm_ee606d3716588b44','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(648,'clm_ee606d3716588b44','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(649,'clm_ee606d3716588b44','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(650,'clm_ee606d3716588b44','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(651,'clm_ee606d3716588b44','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(652,'clm_ee606d3716588b44','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(653,'clm_ee606d3716588b44','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(654,'clm_ee606d3716588b44','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(655,'clm_ee606d3716588b44','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(656,'clm_ee606d3716588b44','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(657,'clm_ee606d3716588b44','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(658,'clm_ee606d3716588b44','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(659,'clm_ee606d3716588b44','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(660,'clm_ee606d3716588b44','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:34:29');
INSERT INTO "claim_evidence_links" VALUES(661,'clm_74e2c971f83ea1e9','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(662,'clm_74e2c971f83ea1e9','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(663,'clm_74e2c971f83ea1e9','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(664,'clm_74e2c971f83ea1e9','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(665,'clm_74e2c971f83ea1e9','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(666,'clm_74e2c971f83ea1e9','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(667,'clm_74e2c971f83ea1e9','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(668,'clm_74e2c971f83ea1e9','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(669,'clm_74e2c971f83ea1e9','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(670,'clm_74e2c971f83ea1e9','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(671,'clm_74e2c971f83ea1e9','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(672,'clm_74e2c971f83ea1e9','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(673,'clm_74e2c971f83ea1e9','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(674,'clm_74e2c971f83ea1e9','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(675,'clm_74e2c971f83ea1e9','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(676,'clm_74e2c971f83ea1e9','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(677,'clm_74e2c971f83ea1e9','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(678,'clm_74e2c971f83ea1e9','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(679,'clm_74e2c971f83ea1e9','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(680,'clm_74e2c971f83ea1e9','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:36:12');
INSERT INTO "claim_evidence_links" VALUES(681,'clm_9f742176be79612b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(682,'clm_9f742176be79612b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(683,'clm_9f742176be79612b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(684,'clm_9f742176be79612b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(685,'clm_9f742176be79612b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(686,'clm_9f742176be79612b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(687,'clm_9f742176be79612b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(688,'clm_9f742176be79612b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(689,'clm_9f742176be79612b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(690,'clm_9f742176be79612b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(691,'clm_9f742176be79612b','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(692,'clm_9f742176be79612b','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(693,'clm_9f742176be79612b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(694,'clm_9f742176be79612b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(695,'clm_9f742176be79612b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(696,'clm_9f742176be79612b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(697,'clm_9f742176be79612b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(698,'clm_9f742176be79612b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(699,'clm_9f742176be79612b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(700,'clm_9f742176be79612b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:36:36');
INSERT INTO "claim_evidence_links" VALUES(701,'clm_efd69c82742a70f0','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(702,'clm_efd69c82742a70f0','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(703,'clm_efd69c82742a70f0','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(704,'clm_efd69c82742a70f0','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(705,'clm_efd69c82742a70f0','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(706,'clm_efd69c82742a70f0','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(707,'clm_efd69c82742a70f0','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(708,'clm_efd69c82742a70f0','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(709,'clm_efd69c82742a70f0','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(710,'clm_efd69c82742a70f0','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(711,'clm_efd69c82742a70f0','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(712,'clm_efd69c82742a70f0','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(713,'clm_efd69c82742a70f0','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(714,'clm_efd69c82742a70f0','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(715,'clm_efd69c82742a70f0','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(716,'clm_efd69c82742a70f0','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(717,'clm_efd69c82742a70f0','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(718,'clm_efd69c82742a70f0','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(719,'clm_efd69c82742a70f0','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(720,'clm_efd69c82742a70f0','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:37:24');
INSERT INTO "claim_evidence_links" VALUES(721,'clm_59dcd9fc72b40e89','ev_fin_02599521cdbed155','supports',0,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(722,'clm_59dcd9fc72b40e89','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(723,'clm_59dcd9fc72b40e89','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(724,'clm_59dcd9fc72b40e89','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(725,'clm_59dcd9fc72b40e89','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(726,'clm_59dcd9fc72b40e89','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(727,'clm_59dcd9fc72b40e89','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(728,'clm_59dcd9fc72b40e89','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(729,'clm_59dcd9fc72b40e89','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(730,'clm_59dcd9fc72b40e89','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(731,'clm_59dcd9fc72b40e89','ev_fin_633671310de9326b','supports',10,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(732,'clm_59dcd9fc72b40e89','ev_fin_464910c137146f73','supports',11,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(733,'clm_59dcd9fc72b40e89','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(734,'clm_59dcd9fc72b40e89','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(735,'clm_59dcd9fc72b40e89','ev_fin_336d435f61d20911','supports',14,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(736,'clm_59dcd9fc72b40e89','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(737,'clm_59dcd9fc72b40e89','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(738,'clm_59dcd9fc72b40e89','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(739,'clm_59dcd9fc72b40e89','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(740,'clm_59dcd9fc72b40e89','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 07:38:57');
INSERT INTO "claim_evidence_links" VALUES(741,'clm_fe9455d62a5e3ec9','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(742,'clm_fe9455d62a5e3ec9','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(743,'clm_fe9455d62a5e3ec9','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(744,'clm_fe9455d62a5e3ec9','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(745,'clm_fe9455d62a5e3ec9','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(746,'clm_fe9455d62a5e3ec9','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(747,'clm_fe9455d62a5e3ec9','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(748,'clm_fe9455d62a5e3ec9','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(749,'clm_fe9455d62a5e3ec9','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(750,'clm_fe9455d62a5e3ec9','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(751,'clm_fe9455d62a5e3ec9','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(752,'clm_fe9455d62a5e3ec9','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(753,'clm_fe9455d62a5e3ec9','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(754,'clm_fe9455d62a5e3ec9','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(755,'clm_fe9455d62a5e3ec9','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(756,'clm_fe9455d62a5e3ec9','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(757,'clm_fe9455d62a5e3ec9','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(758,'clm_fe9455d62a5e3ec9','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(759,'clm_fe9455d62a5e3ec9','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(760,'clm_fe9455d62a5e3ec9','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:29:27');
INSERT INTO "claim_evidence_links" VALUES(761,'clm_3f9cdb7a8d1419e1','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(762,'clm_3f9cdb7a8d1419e1','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(763,'clm_3f9cdb7a8d1419e1','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(764,'clm_3f9cdb7a8d1419e1','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(765,'clm_3f9cdb7a8d1419e1','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(766,'clm_3f9cdb7a8d1419e1','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(767,'clm_3f9cdb7a8d1419e1','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(768,'clm_3f9cdb7a8d1419e1','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(769,'clm_3f9cdb7a8d1419e1','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(770,'clm_3f9cdb7a8d1419e1','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(771,'clm_3f9cdb7a8d1419e1','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(772,'clm_3f9cdb7a8d1419e1','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(773,'clm_3f9cdb7a8d1419e1','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(774,'clm_3f9cdb7a8d1419e1','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(775,'clm_3f9cdb7a8d1419e1','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(776,'clm_3f9cdb7a8d1419e1','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(777,'clm_3f9cdb7a8d1419e1','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(778,'clm_3f9cdb7a8d1419e1','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(779,'clm_3f9cdb7a8d1419e1','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(780,'clm_3f9cdb7a8d1419e1','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:30:40');
INSERT INTO "claim_evidence_links" VALUES(781,'clm_57dd37f32d881858','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(782,'clm_57dd37f32d881858','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(783,'clm_57dd37f32d881858','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(784,'clm_57dd37f32d881858','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(785,'clm_57dd37f32d881858','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(786,'clm_57dd37f32d881858','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(787,'clm_57dd37f32d881858','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(788,'clm_57dd37f32d881858','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(789,'clm_57dd37f32d881858','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(790,'clm_57dd37f32d881858','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(791,'clm_57dd37f32d881858','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(792,'clm_57dd37f32d881858','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(793,'clm_57dd37f32d881858','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(794,'clm_57dd37f32d881858','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(795,'clm_57dd37f32d881858','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(796,'clm_57dd37f32d881858','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(797,'clm_57dd37f32d881858','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(798,'clm_57dd37f32d881858','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(799,'clm_57dd37f32d881858','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(800,'clm_57dd37f32d881858','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:31:24');
INSERT INTO "claim_evidence_links" VALUES(801,'clm_83b85d44589ff246','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(802,'clm_83b85d44589ff246','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(803,'clm_83b85d44589ff246','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(804,'clm_83b85d44589ff246','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(805,'clm_83b85d44589ff246','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(806,'clm_83b85d44589ff246','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(807,'clm_83b85d44589ff246','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(808,'clm_83b85d44589ff246','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(809,'clm_83b85d44589ff246','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(810,'clm_83b85d44589ff246','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(811,'clm_83b85d44589ff246','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(812,'clm_83b85d44589ff246','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(813,'clm_83b85d44589ff246','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(814,'clm_83b85d44589ff246','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(815,'clm_83b85d44589ff246','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(816,'clm_83b85d44589ff246','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(817,'clm_83b85d44589ff246','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(818,'clm_83b85d44589ff246','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(819,'clm_83b85d44589ff246','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(820,'clm_83b85d44589ff246','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:31:26');
INSERT INTO "claim_evidence_links" VALUES(821,'clm_5a7ade3b1327e1a9','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(822,'clm_5a7ade3b1327e1a9','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(823,'clm_5a7ade3b1327e1a9','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(824,'clm_5a7ade3b1327e1a9','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(825,'clm_5a7ade3b1327e1a9','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(826,'clm_5a7ade3b1327e1a9','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(827,'clm_5a7ade3b1327e1a9','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(828,'clm_5a7ade3b1327e1a9','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(829,'clm_5a7ade3b1327e1a9','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(830,'clm_5a7ade3b1327e1a9','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(831,'clm_5a7ade3b1327e1a9','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(832,'clm_5a7ade3b1327e1a9','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(833,'clm_5a7ade3b1327e1a9','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(834,'clm_5a7ade3b1327e1a9','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(835,'clm_5a7ade3b1327e1a9','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(836,'clm_5a7ade3b1327e1a9','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(837,'clm_5a7ade3b1327e1a9','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(838,'clm_5a7ade3b1327e1a9','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(839,'clm_5a7ade3b1327e1a9','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(840,'clm_5a7ade3b1327e1a9','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:31:27');
INSERT INTO "claim_evidence_links" VALUES(841,'clm_b8f6e7db9bed54c9','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(842,'clm_b8f6e7db9bed54c9','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(843,'clm_b8f6e7db9bed54c9','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(844,'clm_b8f6e7db9bed54c9','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(845,'clm_b8f6e7db9bed54c9','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(846,'clm_b8f6e7db9bed54c9','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(847,'clm_b8f6e7db9bed54c9','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(848,'clm_b8f6e7db9bed54c9','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(849,'clm_b8f6e7db9bed54c9','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(850,'clm_b8f6e7db9bed54c9','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(851,'clm_b8f6e7db9bed54c9','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(852,'clm_b8f6e7db9bed54c9','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(853,'clm_b8f6e7db9bed54c9','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(854,'clm_b8f6e7db9bed54c9','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(855,'clm_b8f6e7db9bed54c9','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(856,'clm_b8f6e7db9bed54c9','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(857,'clm_b8f6e7db9bed54c9','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(858,'clm_b8f6e7db9bed54c9','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(859,'clm_b8f6e7db9bed54c9','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(860,'clm_b8f6e7db9bed54c9','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:31:34');
INSERT INTO "claim_evidence_links" VALUES(861,'clm_32ece868a6c4d78e','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(862,'clm_32ece868a6c4d78e','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(863,'clm_32ece868a6c4d78e','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(864,'clm_32ece868a6c4d78e','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(865,'clm_32ece868a6c4d78e','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(866,'clm_32ece868a6c4d78e','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(867,'clm_32ece868a6c4d78e','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(868,'clm_32ece868a6c4d78e','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(869,'clm_32ece868a6c4d78e','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(870,'clm_32ece868a6c4d78e','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(871,'clm_32ece868a6c4d78e','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(872,'clm_32ece868a6c4d78e','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(873,'clm_32ece868a6c4d78e','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(874,'clm_32ece868a6c4d78e','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(875,'clm_32ece868a6c4d78e','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(876,'clm_32ece868a6c4d78e','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(877,'clm_32ece868a6c4d78e','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(878,'clm_32ece868a6c4d78e','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(879,'clm_32ece868a6c4d78e','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(880,'clm_32ece868a6c4d78e','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:32:58');
INSERT INTO "claim_evidence_links" VALUES(881,'clm_c395b3088f333cb9','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(882,'clm_c395b3088f333cb9','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(883,'clm_c395b3088f333cb9','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(884,'clm_c395b3088f333cb9','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(885,'clm_c395b3088f333cb9','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(886,'clm_c395b3088f333cb9','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(887,'clm_c395b3088f333cb9','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(888,'clm_c395b3088f333cb9','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(889,'clm_c395b3088f333cb9','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(890,'clm_c395b3088f333cb9','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(891,'clm_c395b3088f333cb9','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(892,'clm_c395b3088f333cb9','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(893,'clm_c395b3088f333cb9','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(894,'clm_c395b3088f333cb9','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(895,'clm_c395b3088f333cb9','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(896,'clm_c395b3088f333cb9','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(897,'clm_c395b3088f333cb9','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(898,'clm_c395b3088f333cb9','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(899,'clm_c395b3088f333cb9','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(900,'clm_c395b3088f333cb9','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:33:09');
INSERT INTO "claim_evidence_links" VALUES(901,'clm_72c09be7538b5cd8','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(902,'clm_72c09be7538b5cd8','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(903,'clm_72c09be7538b5cd8','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(904,'clm_72c09be7538b5cd8','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(905,'clm_72c09be7538b5cd8','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(906,'clm_72c09be7538b5cd8','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(907,'clm_72c09be7538b5cd8','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(908,'clm_72c09be7538b5cd8','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(909,'clm_72c09be7538b5cd8','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(910,'clm_72c09be7538b5cd8','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(911,'clm_72c09be7538b5cd8','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(912,'clm_72c09be7538b5cd8','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(913,'clm_72c09be7538b5cd8','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(914,'clm_72c09be7538b5cd8','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(915,'clm_72c09be7538b5cd8','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(916,'clm_72c09be7538b5cd8','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(917,'clm_72c09be7538b5cd8','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(918,'clm_72c09be7538b5cd8','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(919,'clm_72c09be7538b5cd8','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(920,'clm_72c09be7538b5cd8','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:34:31');
INSERT INTO "claim_evidence_links" VALUES(921,'clm_cbfba9b476448c60','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(922,'clm_cbfba9b476448c60','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(923,'clm_cbfba9b476448c60','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(924,'clm_cbfba9b476448c60','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(925,'clm_cbfba9b476448c60','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(926,'clm_cbfba9b476448c60','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(927,'clm_cbfba9b476448c60','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(928,'clm_cbfba9b476448c60','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(929,'clm_cbfba9b476448c60','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(930,'clm_cbfba9b476448c60','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(931,'clm_cbfba9b476448c60','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(932,'clm_cbfba9b476448c60','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(933,'clm_cbfba9b476448c60','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(934,'clm_cbfba9b476448c60','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(935,'clm_cbfba9b476448c60','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(936,'clm_cbfba9b476448c60','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(937,'clm_cbfba9b476448c60','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(938,'clm_cbfba9b476448c60','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(939,'clm_cbfba9b476448c60','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(940,'clm_cbfba9b476448c60','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:34:42');
INSERT INTO "claim_evidence_links" VALUES(941,'clm_06224b62d16ebb93','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(942,'clm_06224b62d16ebb93','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(943,'clm_06224b62d16ebb93','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(944,'clm_06224b62d16ebb93','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(945,'clm_06224b62d16ebb93','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(946,'clm_06224b62d16ebb93','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(947,'clm_06224b62d16ebb93','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(948,'clm_06224b62d16ebb93','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(949,'clm_06224b62d16ebb93','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(950,'clm_06224b62d16ebb93','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(951,'clm_06224b62d16ebb93','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(952,'clm_06224b62d16ebb93','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(953,'clm_06224b62d16ebb93','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(954,'clm_06224b62d16ebb93','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(955,'clm_06224b62d16ebb93','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(956,'clm_06224b62d16ebb93','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(957,'clm_06224b62d16ebb93','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(958,'clm_06224b62d16ebb93','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(959,'clm_06224b62d16ebb93','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(960,'clm_06224b62d16ebb93','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:36:05');
INSERT INTO "claim_evidence_links" VALUES(961,'clm_aa6f82ad2d3327d7','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(962,'clm_aa6f82ad2d3327d7','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(963,'clm_aa6f82ad2d3327d7','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(964,'clm_aa6f82ad2d3327d7','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(965,'clm_aa6f82ad2d3327d7','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(966,'clm_aa6f82ad2d3327d7','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(967,'clm_aa6f82ad2d3327d7','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(968,'clm_aa6f82ad2d3327d7','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(969,'clm_aa6f82ad2d3327d7','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(970,'clm_aa6f82ad2d3327d7','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(971,'clm_aa6f82ad2d3327d7','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(972,'clm_aa6f82ad2d3327d7','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(973,'clm_aa6f82ad2d3327d7','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(974,'clm_aa6f82ad2d3327d7','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(975,'clm_aa6f82ad2d3327d7','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(976,'clm_aa6f82ad2d3327d7','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(977,'clm_aa6f82ad2d3327d7','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(978,'clm_aa6f82ad2d3327d7','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(979,'clm_aa6f82ad2d3327d7','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(980,'clm_aa6f82ad2d3327d7','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:36:15');
INSERT INTO "claim_evidence_links" VALUES(981,'clm_ccb41ceae53614ec','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(982,'clm_ccb41ceae53614ec','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(983,'clm_ccb41ceae53614ec','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(984,'clm_ccb41ceae53614ec','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(985,'clm_ccb41ceae53614ec','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(986,'clm_ccb41ceae53614ec','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(987,'clm_ccb41ceae53614ec','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(988,'clm_ccb41ceae53614ec','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(989,'clm_ccb41ceae53614ec','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(990,'clm_ccb41ceae53614ec','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(991,'clm_ccb41ceae53614ec','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(992,'clm_ccb41ceae53614ec','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(993,'clm_ccb41ceae53614ec','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(994,'clm_ccb41ceae53614ec','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(995,'clm_ccb41ceae53614ec','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(996,'clm_ccb41ceae53614ec','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(997,'clm_ccb41ceae53614ec','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(998,'clm_ccb41ceae53614ec','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(999,'clm_ccb41ceae53614ec','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(1000,'clm_ccb41ceae53614ec','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:37:21');
INSERT INTO "claim_evidence_links" VALUES(1001,'clm_9e0bdb0fbca816bd','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1002,'clm_9e0bdb0fbca816bd','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1003,'clm_9e0bdb0fbca816bd','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1004,'clm_9e0bdb0fbca816bd','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1005,'clm_9e0bdb0fbca816bd','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1006,'clm_9e0bdb0fbca816bd','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1007,'clm_9e0bdb0fbca816bd','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1008,'clm_9e0bdb0fbca816bd','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1009,'clm_9e0bdb0fbca816bd','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1010,'clm_9e0bdb0fbca816bd','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1011,'clm_9e0bdb0fbca816bd','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1012,'clm_9e0bdb0fbca816bd','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1013,'clm_9e0bdb0fbca816bd','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1014,'clm_9e0bdb0fbca816bd','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1015,'clm_9e0bdb0fbca816bd','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1016,'clm_9e0bdb0fbca816bd','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1017,'clm_9e0bdb0fbca816bd','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1018,'clm_9e0bdb0fbca816bd','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1019,'clm_9e0bdb0fbca816bd','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1020,'clm_9e0bdb0fbca816bd','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:37:27');
INSERT INTO "claim_evidence_links" VALUES(1021,'clm_99408cedf61ab1be','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1022,'clm_99408cedf61ab1be','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1023,'clm_99408cedf61ab1be','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1024,'clm_99408cedf61ab1be','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1025,'clm_99408cedf61ab1be','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1026,'clm_99408cedf61ab1be','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1027,'clm_99408cedf61ab1be','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1028,'clm_99408cedf61ab1be','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1029,'clm_99408cedf61ab1be','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1030,'clm_99408cedf61ab1be','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1031,'clm_99408cedf61ab1be','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1032,'clm_99408cedf61ab1be','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1033,'clm_99408cedf61ab1be','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1034,'clm_99408cedf61ab1be','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1035,'clm_99408cedf61ab1be','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1036,'clm_99408cedf61ab1be','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1037,'clm_99408cedf61ab1be','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1038,'clm_99408cedf61ab1be','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1039,'clm_99408cedf61ab1be','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1040,'clm_99408cedf61ab1be','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:37:32');
INSERT INTO "claim_evidence_links" VALUES(1041,'clm_e22b0c978e351169','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1042,'clm_e22b0c978e351169','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1043,'clm_e22b0c978e351169','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1044,'clm_e22b0c978e351169','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1045,'clm_e22b0c978e351169','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1046,'clm_e22b0c978e351169','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1047,'clm_e22b0c978e351169','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1048,'clm_e22b0c978e351169','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1049,'clm_e22b0c978e351169','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1050,'clm_e22b0c978e351169','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1051,'clm_e22b0c978e351169','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1052,'clm_e22b0c978e351169','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1053,'clm_e22b0c978e351169','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1054,'clm_e22b0c978e351169','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1055,'clm_e22b0c978e351169','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1056,'clm_e22b0c978e351169','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1057,'clm_e22b0c978e351169','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1058,'clm_e22b0c978e351169','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1059,'clm_e22b0c978e351169','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1060,'clm_e22b0c978e351169','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:37:38');
INSERT INTO "claim_evidence_links" VALUES(1061,'clm_9706ec36fc7a92de','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1062,'clm_9706ec36fc7a92de','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1063,'clm_9706ec36fc7a92de','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1064,'clm_9706ec36fc7a92de','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1065,'clm_9706ec36fc7a92de','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1066,'clm_9706ec36fc7a92de','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1067,'clm_9706ec36fc7a92de','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1068,'clm_9706ec36fc7a92de','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1069,'clm_9706ec36fc7a92de','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1070,'clm_9706ec36fc7a92de','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1071,'clm_9706ec36fc7a92de','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1072,'clm_9706ec36fc7a92de','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1073,'clm_9706ec36fc7a92de','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1074,'clm_9706ec36fc7a92de','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1075,'clm_9706ec36fc7a92de','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1076,'clm_9706ec36fc7a92de','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1077,'clm_9706ec36fc7a92de','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1078,'clm_9706ec36fc7a92de','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1079,'clm_9706ec36fc7a92de','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1080,'clm_9706ec36fc7a92de','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:37:48');
INSERT INTO "claim_evidence_links" VALUES(1081,'clm_7301fc3ea57db886','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1082,'clm_7301fc3ea57db886','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1083,'clm_7301fc3ea57db886','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1084,'clm_7301fc3ea57db886','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1085,'clm_7301fc3ea57db886','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1086,'clm_7301fc3ea57db886','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1087,'clm_7301fc3ea57db886','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1088,'clm_7301fc3ea57db886','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1089,'clm_7301fc3ea57db886','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1090,'clm_7301fc3ea57db886','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1091,'clm_7301fc3ea57db886','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1092,'clm_7301fc3ea57db886','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1093,'clm_7301fc3ea57db886','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1094,'clm_7301fc3ea57db886','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1095,'clm_7301fc3ea57db886','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1096,'clm_7301fc3ea57db886','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1097,'clm_7301fc3ea57db886','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1098,'clm_7301fc3ea57db886','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1099,'clm_7301fc3ea57db886','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1100,'clm_7301fc3ea57db886','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:39:11');
INSERT INTO "claim_evidence_links" VALUES(1101,'clm_8e837a51f94e76b5','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1102,'clm_8e837a51f94e76b5','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1103,'clm_8e837a51f94e76b5','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1104,'clm_8e837a51f94e76b5','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1105,'clm_8e837a51f94e76b5','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1106,'clm_8e837a51f94e76b5','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1107,'clm_8e837a51f94e76b5','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1108,'clm_8e837a51f94e76b5','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1109,'clm_8e837a51f94e76b5','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1110,'clm_8e837a51f94e76b5','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1111,'clm_8e837a51f94e76b5','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1112,'clm_8e837a51f94e76b5','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1113,'clm_8e837a51f94e76b5','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1114,'clm_8e837a51f94e76b5','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1115,'clm_8e837a51f94e76b5','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1116,'clm_8e837a51f94e76b5','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1117,'clm_8e837a51f94e76b5','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1118,'clm_8e837a51f94e76b5','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1119,'clm_8e837a51f94e76b5','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1120,'clm_8e837a51f94e76b5','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:39:21');
INSERT INTO "claim_evidence_links" VALUES(1121,'clm_77ce8716d19a4745','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1122,'clm_77ce8716d19a4745','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1123,'clm_77ce8716d19a4745','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1124,'clm_77ce8716d19a4745','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1125,'clm_77ce8716d19a4745','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1126,'clm_77ce8716d19a4745','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1127,'clm_77ce8716d19a4745','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1128,'clm_77ce8716d19a4745','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1129,'clm_77ce8716d19a4745','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1130,'clm_77ce8716d19a4745','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1131,'clm_77ce8716d19a4745','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1132,'clm_77ce8716d19a4745','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1133,'clm_77ce8716d19a4745','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1134,'clm_77ce8716d19a4745','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1135,'clm_77ce8716d19a4745','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1136,'clm_77ce8716d19a4745','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1137,'clm_77ce8716d19a4745','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1138,'clm_77ce8716d19a4745','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1139,'clm_77ce8716d19a4745','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1140,'clm_77ce8716d19a4745','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:39:53');
INSERT INTO "claim_evidence_links" VALUES(1141,'clm_c0fe0787b99bd861','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1142,'clm_c0fe0787b99bd861','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1143,'clm_c0fe0787b99bd861','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1144,'clm_c0fe0787b99bd861','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1145,'clm_c0fe0787b99bd861','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1146,'clm_c0fe0787b99bd861','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1147,'clm_c0fe0787b99bd861','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1148,'clm_c0fe0787b99bd861','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1149,'clm_c0fe0787b99bd861','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1150,'clm_c0fe0787b99bd861','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1151,'clm_c0fe0787b99bd861','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1152,'clm_c0fe0787b99bd861','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1153,'clm_c0fe0787b99bd861','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1154,'clm_c0fe0787b99bd861','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1155,'clm_c0fe0787b99bd861','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1156,'clm_c0fe0787b99bd861','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1157,'clm_c0fe0787b99bd861','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1158,'clm_c0fe0787b99bd861','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1159,'clm_c0fe0787b99bd861','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1160,'clm_c0fe0787b99bd861','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:41:28');
INSERT INTO "claim_evidence_links" VALUES(1161,'clm_451d15cec2615e80','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1162,'clm_451d15cec2615e80','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1163,'clm_451d15cec2615e80','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1164,'clm_451d15cec2615e80','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1165,'clm_451d15cec2615e80','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1166,'clm_451d15cec2615e80','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1167,'clm_451d15cec2615e80','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1168,'clm_451d15cec2615e80','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1169,'clm_451d15cec2615e80','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1170,'clm_451d15cec2615e80','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1171,'clm_451d15cec2615e80','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1172,'clm_451d15cec2615e80','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1173,'clm_451d15cec2615e80','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1174,'clm_451d15cec2615e80','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1175,'clm_451d15cec2615e80','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1176,'clm_451d15cec2615e80','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1177,'clm_451d15cec2615e80','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1178,'clm_451d15cec2615e80','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1179,'clm_451d15cec2615e80','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1180,'clm_451d15cec2615e80','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:43:00');
INSERT INTO "claim_evidence_links" VALUES(1181,'clm_c200a59f876e1e58','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1182,'clm_c200a59f876e1e58','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1183,'clm_c200a59f876e1e58','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1184,'clm_c200a59f876e1e58','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1185,'clm_c200a59f876e1e58','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1186,'clm_c200a59f876e1e58','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1187,'clm_c200a59f876e1e58','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1188,'clm_c200a59f876e1e58','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1189,'clm_c200a59f876e1e58','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1190,'clm_c200a59f876e1e58','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1191,'clm_c200a59f876e1e58','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1192,'clm_c200a59f876e1e58','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1193,'clm_c200a59f876e1e58','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1194,'clm_c200a59f876e1e58','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1195,'clm_c200a59f876e1e58','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1196,'clm_c200a59f876e1e58','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1197,'clm_c200a59f876e1e58','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1198,'clm_c200a59f876e1e58','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1199,'clm_c200a59f876e1e58','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1200,'clm_c200a59f876e1e58','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:44:33');
INSERT INTO "claim_evidence_links" VALUES(1201,'clm_1d1b8907ed55f552','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1202,'clm_1d1b8907ed55f552','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1203,'clm_1d1b8907ed55f552','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1204,'clm_1d1b8907ed55f552','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1205,'clm_1d1b8907ed55f552','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1206,'clm_1d1b8907ed55f552','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1207,'clm_1d1b8907ed55f552','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1208,'clm_1d1b8907ed55f552','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1209,'clm_1d1b8907ed55f552','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1210,'clm_1d1b8907ed55f552','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1211,'clm_1d1b8907ed55f552','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1212,'clm_1d1b8907ed55f552','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1213,'clm_1d1b8907ed55f552','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1214,'clm_1d1b8907ed55f552','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1215,'clm_1d1b8907ed55f552','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1216,'clm_1d1b8907ed55f552','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1217,'clm_1d1b8907ed55f552','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1218,'clm_1d1b8907ed55f552','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1219,'clm_1d1b8907ed55f552','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1220,'clm_1d1b8907ed55f552','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:46:06');
INSERT INTO "claim_evidence_links" VALUES(1221,'clm_538889b54c6036aa','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1222,'clm_538889b54c6036aa','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1223,'clm_538889b54c6036aa','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1224,'clm_538889b54c6036aa','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1225,'clm_538889b54c6036aa','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1226,'clm_538889b54c6036aa','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1227,'clm_538889b54c6036aa','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1228,'clm_538889b54c6036aa','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1229,'clm_538889b54c6036aa','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1230,'clm_538889b54c6036aa','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1231,'clm_538889b54c6036aa','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1232,'clm_538889b54c6036aa','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1233,'clm_538889b54c6036aa','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1234,'clm_538889b54c6036aa','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1235,'clm_538889b54c6036aa','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1236,'clm_538889b54c6036aa','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1237,'clm_538889b54c6036aa','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1238,'clm_538889b54c6036aa','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1239,'clm_538889b54c6036aa','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1240,'clm_538889b54c6036aa','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:47:42');
INSERT INTO "claim_evidence_links" VALUES(1241,'clm_a20f3597c49dfe79','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1242,'clm_a20f3597c49dfe79','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1243,'clm_a20f3597c49dfe79','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1244,'clm_a20f3597c49dfe79','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1245,'clm_a20f3597c49dfe79','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1246,'clm_a20f3597c49dfe79','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1247,'clm_a20f3597c49dfe79','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1248,'clm_a20f3597c49dfe79','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1249,'clm_a20f3597c49dfe79','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1250,'clm_a20f3597c49dfe79','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1251,'clm_a20f3597c49dfe79','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1252,'clm_a20f3597c49dfe79','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1253,'clm_a20f3597c49dfe79','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1254,'clm_a20f3597c49dfe79','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1255,'clm_a20f3597c49dfe79','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1256,'clm_a20f3597c49dfe79','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1257,'clm_a20f3597c49dfe79','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1258,'clm_a20f3597c49dfe79','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1259,'clm_a20f3597c49dfe79','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1260,'clm_a20f3597c49dfe79','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:49:17');
INSERT INTO "claim_evidence_links" VALUES(1261,'clm_0f9ceecbc94033fb','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1262,'clm_0f9ceecbc94033fb','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1263,'clm_0f9ceecbc94033fb','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1264,'clm_0f9ceecbc94033fb','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1265,'clm_0f9ceecbc94033fb','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1266,'clm_0f9ceecbc94033fb','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1267,'clm_0f9ceecbc94033fb','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1268,'clm_0f9ceecbc94033fb','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1269,'clm_0f9ceecbc94033fb','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1270,'clm_0f9ceecbc94033fb','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1271,'clm_0f9ceecbc94033fb','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1272,'clm_0f9ceecbc94033fb','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1273,'clm_0f9ceecbc94033fb','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1274,'clm_0f9ceecbc94033fb','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1275,'clm_0f9ceecbc94033fb','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1276,'clm_0f9ceecbc94033fb','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1277,'clm_0f9ceecbc94033fb','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1278,'clm_0f9ceecbc94033fb','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1279,'clm_0f9ceecbc94033fb','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1280,'clm_0f9ceecbc94033fb','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:50:39');
INSERT INTO "claim_evidence_links" VALUES(1281,'clm_6ea20263b9d3f7e6','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1282,'clm_6ea20263b9d3f7e6','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1283,'clm_6ea20263b9d3f7e6','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1284,'clm_6ea20263b9d3f7e6','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1285,'clm_6ea20263b9d3f7e6','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1286,'clm_6ea20263b9d3f7e6','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1287,'clm_6ea20263b9d3f7e6','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1288,'clm_6ea20263b9d3f7e6','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1289,'clm_6ea20263b9d3f7e6','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1290,'clm_6ea20263b9d3f7e6','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1291,'clm_6ea20263b9d3f7e6','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1292,'clm_6ea20263b9d3f7e6','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1293,'clm_6ea20263b9d3f7e6','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1294,'clm_6ea20263b9d3f7e6','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1295,'clm_6ea20263b9d3f7e6','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1296,'clm_6ea20263b9d3f7e6','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1297,'clm_6ea20263b9d3f7e6','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1298,'clm_6ea20263b9d3f7e6','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1299,'clm_6ea20263b9d3f7e6','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1300,'clm_6ea20263b9d3f7e6','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:52:12');
INSERT INTO "claim_evidence_links" VALUES(1301,'clm_dab6deb6bd805a30','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1302,'clm_dab6deb6bd805a30','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1303,'clm_dab6deb6bd805a30','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1304,'clm_dab6deb6bd805a30','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1305,'clm_dab6deb6bd805a30','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1306,'clm_dab6deb6bd805a30','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1307,'clm_dab6deb6bd805a30','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1308,'clm_dab6deb6bd805a30','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1309,'clm_dab6deb6bd805a30','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1310,'clm_dab6deb6bd805a30','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1311,'clm_dab6deb6bd805a30','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1312,'clm_dab6deb6bd805a30','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1313,'clm_dab6deb6bd805a30','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1314,'clm_dab6deb6bd805a30','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1315,'clm_dab6deb6bd805a30','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1316,'clm_dab6deb6bd805a30','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1317,'clm_dab6deb6bd805a30','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1318,'clm_dab6deb6bd805a30','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1319,'clm_dab6deb6bd805a30','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1320,'clm_dab6deb6bd805a30','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:53:45');
INSERT INTO "claim_evidence_links" VALUES(1321,'clm_81218d250f701a33','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1322,'clm_81218d250f701a33','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1323,'clm_81218d250f701a33','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1324,'clm_81218d250f701a33','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1325,'clm_81218d250f701a33','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1326,'clm_81218d250f701a33','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1327,'clm_81218d250f701a33','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1328,'clm_81218d250f701a33','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1329,'clm_81218d250f701a33','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1330,'clm_81218d250f701a33','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1331,'clm_81218d250f701a33','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1332,'clm_81218d250f701a33','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1333,'clm_81218d250f701a33','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1334,'clm_81218d250f701a33','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1335,'clm_81218d250f701a33','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1336,'clm_81218d250f701a33','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1337,'clm_81218d250f701a33','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1338,'clm_81218d250f701a33','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1339,'clm_81218d250f701a33','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1340,'clm_81218d250f701a33','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:55:19');
INSERT INTO "claim_evidence_links" VALUES(1341,'clm_98e312df1f670dcd','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1342,'clm_98e312df1f670dcd','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1343,'clm_98e312df1f670dcd','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1344,'clm_98e312df1f670dcd','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1345,'clm_98e312df1f670dcd','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1346,'clm_98e312df1f670dcd','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1347,'clm_98e312df1f670dcd','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1348,'clm_98e312df1f670dcd','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1349,'clm_98e312df1f670dcd','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1350,'clm_98e312df1f670dcd','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1351,'clm_98e312df1f670dcd','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1352,'clm_98e312df1f670dcd','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1353,'clm_98e312df1f670dcd','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1354,'clm_98e312df1f670dcd','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1355,'clm_98e312df1f670dcd','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1356,'clm_98e312df1f670dcd','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1357,'clm_98e312df1f670dcd','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1358,'clm_98e312df1f670dcd','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1359,'clm_98e312df1f670dcd','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1360,'clm_98e312df1f670dcd','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:56:52');
INSERT INTO "claim_evidence_links" VALUES(1361,'clm_a715a3d3da6f0462','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1362,'clm_a715a3d3da6f0462','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1363,'clm_a715a3d3da6f0462','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1364,'clm_a715a3d3da6f0462','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1365,'clm_a715a3d3da6f0462','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1366,'clm_a715a3d3da6f0462','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1367,'clm_a715a3d3da6f0462','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1368,'clm_a715a3d3da6f0462','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1369,'clm_a715a3d3da6f0462','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1370,'clm_a715a3d3da6f0462','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1371,'clm_a715a3d3da6f0462','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1372,'clm_a715a3d3da6f0462','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1373,'clm_a715a3d3da6f0462','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1374,'clm_a715a3d3da6f0462','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1375,'clm_a715a3d3da6f0462','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1376,'clm_a715a3d3da6f0462','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1377,'clm_a715a3d3da6f0462','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1378,'clm_a715a3d3da6f0462','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1379,'clm_a715a3d3da6f0462','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1380,'clm_a715a3d3da6f0462','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:58:25');
INSERT INTO "claim_evidence_links" VALUES(1381,'clm_e9108af353a1ba19','ev_fin_02599521cdbed155','supports',0,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1382,'clm_e9108af353a1ba19','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1383,'clm_e9108af353a1ba19','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1384,'clm_e9108af353a1ba19','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1385,'clm_e9108af353a1ba19','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1386,'clm_e9108af353a1ba19','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1387,'clm_e9108af353a1ba19','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1388,'clm_e9108af353a1ba19','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1389,'clm_e9108af353a1ba19','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1390,'clm_e9108af353a1ba19','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1391,'clm_e9108af353a1ba19','ev_fin_633671310de9326b','supports',10,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1392,'clm_e9108af353a1ba19','ev_fin_464910c137146f73','supports',11,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1393,'clm_e9108af353a1ba19','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1394,'clm_e9108af353a1ba19','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1395,'clm_e9108af353a1ba19','ev_fin_336d435f61d20911','supports',14,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1396,'clm_e9108af353a1ba19','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1397,'clm_e9108af353a1ba19','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1398,'clm_e9108af353a1ba19','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1399,'clm_e9108af353a1ba19','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1400,'clm_e9108af353a1ba19','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 09:59:59');
INSERT INTO "claim_evidence_links" VALUES(1401,'clm_123202cd3d207010','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1402,'clm_123202cd3d207010','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1403,'clm_123202cd3d207010','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1404,'clm_123202cd3d207010','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1405,'clm_123202cd3d207010','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1406,'clm_123202cd3d207010','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1407,'clm_123202cd3d207010','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1408,'clm_123202cd3d207010','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1409,'clm_123202cd3d207010','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1410,'clm_123202cd3d207010','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1411,'clm_123202cd3d207010','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1412,'clm_123202cd3d207010','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1413,'clm_123202cd3d207010','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1414,'clm_123202cd3d207010','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1415,'clm_123202cd3d207010','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1416,'clm_123202cd3d207010','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1417,'clm_123202cd3d207010','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1418,'clm_123202cd3d207010','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1419,'clm_123202cd3d207010','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1420,'clm_123202cd3d207010','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:01:11');
INSERT INTO "claim_evidence_links" VALUES(1421,'clm_1e9448916689c433','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1422,'clm_1e9448916689c433','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1423,'clm_1e9448916689c433','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1424,'clm_1e9448916689c433','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1425,'clm_1e9448916689c433','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1426,'clm_1e9448916689c433','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1427,'clm_1e9448916689c433','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1428,'clm_1e9448916689c433','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1429,'clm_1e9448916689c433','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1430,'clm_1e9448916689c433','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1431,'clm_1e9448916689c433','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1432,'clm_1e9448916689c433','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1433,'clm_1e9448916689c433','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1434,'clm_1e9448916689c433','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1435,'clm_1e9448916689c433','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1436,'clm_1e9448916689c433','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1437,'clm_1e9448916689c433','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1438,'clm_1e9448916689c433','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1439,'clm_1e9448916689c433','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1440,'clm_1e9448916689c433','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:02:44');
INSERT INTO "claim_evidence_links" VALUES(1441,'clm_7eac4f776722e850','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1442,'clm_7eac4f776722e850','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1443,'clm_7eac4f776722e850','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1444,'clm_7eac4f776722e850','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1445,'clm_7eac4f776722e850','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1446,'clm_7eac4f776722e850','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1447,'clm_7eac4f776722e850','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1448,'clm_7eac4f776722e850','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1449,'clm_7eac4f776722e850','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1450,'clm_7eac4f776722e850','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1451,'clm_7eac4f776722e850','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1452,'clm_7eac4f776722e850','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1453,'clm_7eac4f776722e850','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1454,'clm_7eac4f776722e850','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1455,'clm_7eac4f776722e850','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1456,'clm_7eac4f776722e850','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1457,'clm_7eac4f776722e850','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1458,'clm_7eac4f776722e850','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1459,'clm_7eac4f776722e850','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1460,'clm_7eac4f776722e850','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:04:17');
INSERT INTO "claim_evidence_links" VALUES(1461,'clm_ab2a6cadc513cd00','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1462,'clm_ab2a6cadc513cd00','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1463,'clm_ab2a6cadc513cd00','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1464,'clm_ab2a6cadc513cd00','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1465,'clm_ab2a6cadc513cd00','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1466,'clm_ab2a6cadc513cd00','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1467,'clm_ab2a6cadc513cd00','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1468,'clm_ab2a6cadc513cd00','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1469,'clm_ab2a6cadc513cd00','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1470,'clm_ab2a6cadc513cd00','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1471,'clm_ab2a6cadc513cd00','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1472,'clm_ab2a6cadc513cd00','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1473,'clm_ab2a6cadc513cd00','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1474,'clm_ab2a6cadc513cd00','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1475,'clm_ab2a6cadc513cd00','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1476,'clm_ab2a6cadc513cd00','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1477,'clm_ab2a6cadc513cd00','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1478,'clm_ab2a6cadc513cd00','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1479,'clm_ab2a6cadc513cd00','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1480,'clm_ab2a6cadc513cd00','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:06:21');
INSERT INTO "claim_evidence_links" VALUES(1481,'clm_04bb9e82c61e7f2f','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1482,'clm_04bb9e82c61e7f2f','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1483,'clm_04bb9e82c61e7f2f','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1484,'clm_04bb9e82c61e7f2f','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1485,'clm_04bb9e82c61e7f2f','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1486,'clm_04bb9e82c61e7f2f','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1487,'clm_04bb9e82c61e7f2f','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1488,'clm_04bb9e82c61e7f2f','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1489,'clm_04bb9e82c61e7f2f','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1490,'clm_04bb9e82c61e7f2f','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1491,'clm_04bb9e82c61e7f2f','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1492,'clm_04bb9e82c61e7f2f','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1493,'clm_04bb9e82c61e7f2f','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1494,'clm_04bb9e82c61e7f2f','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1495,'clm_04bb9e82c61e7f2f','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1496,'clm_04bb9e82c61e7f2f','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1497,'clm_04bb9e82c61e7f2f','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1498,'clm_04bb9e82c61e7f2f','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1499,'clm_04bb9e82c61e7f2f','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1500,'clm_04bb9e82c61e7f2f','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:06:24');
INSERT INTO "claim_evidence_links" VALUES(1501,'clm_52e555c7b5d9929c','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1502,'clm_52e555c7b5d9929c','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1503,'clm_52e555c7b5d9929c','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1504,'clm_52e555c7b5d9929c','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1505,'clm_52e555c7b5d9929c','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1506,'clm_52e555c7b5d9929c','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1507,'clm_52e555c7b5d9929c','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1508,'clm_52e555c7b5d9929c','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1509,'clm_52e555c7b5d9929c','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1510,'clm_52e555c7b5d9929c','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1511,'clm_52e555c7b5d9929c','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1512,'clm_52e555c7b5d9929c','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1513,'clm_52e555c7b5d9929c','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1514,'clm_52e555c7b5d9929c','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1515,'clm_52e555c7b5d9929c','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1516,'clm_52e555c7b5d9929c','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1517,'clm_52e555c7b5d9929c','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1518,'clm_52e555c7b5d9929c','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1519,'clm_52e555c7b5d9929c','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1520,'clm_52e555c7b5d9929c','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:06:26');
INSERT INTO "claim_evidence_links" VALUES(1521,'clm_b7de51a2aca9b1d4','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1522,'clm_b7de51a2aca9b1d4','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1523,'clm_b7de51a2aca9b1d4','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1524,'clm_b7de51a2aca9b1d4','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1525,'clm_b7de51a2aca9b1d4','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1526,'clm_b7de51a2aca9b1d4','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1527,'clm_b7de51a2aca9b1d4','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1528,'clm_b7de51a2aca9b1d4','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1529,'clm_b7de51a2aca9b1d4','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1530,'clm_b7de51a2aca9b1d4','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1531,'clm_b7de51a2aca9b1d4','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1532,'clm_b7de51a2aca9b1d4','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1533,'clm_b7de51a2aca9b1d4','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1534,'clm_b7de51a2aca9b1d4','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1535,'clm_b7de51a2aca9b1d4','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1536,'clm_b7de51a2aca9b1d4','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1537,'clm_b7de51a2aca9b1d4','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1538,'clm_b7de51a2aca9b1d4','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1539,'clm_b7de51a2aca9b1d4','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1540,'clm_b7de51a2aca9b1d4','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:07:54');
INSERT INTO "claim_evidence_links" VALUES(1541,'clm_e6234d16d3fffffe','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1542,'clm_e6234d16d3fffffe','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1543,'clm_e6234d16d3fffffe','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1544,'clm_e6234d16d3fffffe','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1545,'clm_e6234d16d3fffffe','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1546,'clm_e6234d16d3fffffe','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1547,'clm_e6234d16d3fffffe','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1548,'clm_e6234d16d3fffffe','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1549,'clm_e6234d16d3fffffe','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1550,'clm_e6234d16d3fffffe','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1551,'clm_e6234d16d3fffffe','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1552,'clm_e6234d16d3fffffe','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1553,'clm_e6234d16d3fffffe','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1554,'clm_e6234d16d3fffffe','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1555,'clm_e6234d16d3fffffe','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1556,'clm_e6234d16d3fffffe','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1557,'clm_e6234d16d3fffffe','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1558,'clm_e6234d16d3fffffe','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1559,'clm_e6234d16d3fffffe','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1560,'clm_e6234d16d3fffffe','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:03');
INSERT INTO "claim_evidence_links" VALUES(1561,'clm_b88bd007c1ec8270','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1562,'clm_b88bd007c1ec8270','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1563,'clm_b88bd007c1ec8270','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1564,'clm_b88bd007c1ec8270','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1565,'clm_b88bd007c1ec8270','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1566,'clm_b88bd007c1ec8270','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1567,'clm_b88bd007c1ec8270','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1568,'clm_b88bd007c1ec8270','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1569,'clm_b88bd007c1ec8270','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1570,'clm_b88bd007c1ec8270','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1571,'clm_b88bd007c1ec8270','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1572,'clm_b88bd007c1ec8270','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1573,'clm_b88bd007c1ec8270','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1574,'clm_b88bd007c1ec8270','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1575,'clm_b88bd007c1ec8270','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1576,'clm_b88bd007c1ec8270','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1577,'clm_b88bd007c1ec8270','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1578,'clm_b88bd007c1ec8270','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1579,'clm_b88bd007c1ec8270','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1580,'clm_b88bd007c1ec8270','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:04');
INSERT INTO "claim_evidence_links" VALUES(1581,'clm_d724964db326bb65','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1582,'clm_d724964db326bb65','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1583,'clm_d724964db326bb65','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1584,'clm_d724964db326bb65','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1585,'clm_d724964db326bb65','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1586,'clm_d724964db326bb65','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1587,'clm_d724964db326bb65','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1588,'clm_d724964db326bb65','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1589,'clm_d724964db326bb65','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1590,'clm_d724964db326bb65','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1591,'clm_d724964db326bb65','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1592,'clm_d724964db326bb65','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1593,'clm_d724964db326bb65','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1594,'clm_d724964db326bb65','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1595,'clm_d724964db326bb65','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1596,'clm_d724964db326bb65','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1597,'clm_d724964db326bb65','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1598,'clm_d724964db326bb65','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1599,'clm_d724964db326bb65','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1600,'clm_d724964db326bb65','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:05');
INSERT INTO "claim_evidence_links" VALUES(1601,'clm_6517fbbbcb96c8a3','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1602,'clm_6517fbbbcb96c8a3','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1603,'clm_6517fbbbcb96c8a3','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1604,'clm_6517fbbbcb96c8a3','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1605,'clm_6517fbbbcb96c8a3','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1606,'clm_6517fbbbcb96c8a3','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1607,'clm_6517fbbbcb96c8a3','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1608,'clm_6517fbbbcb96c8a3','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1609,'clm_6517fbbbcb96c8a3','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1610,'clm_6517fbbbcb96c8a3','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1611,'clm_6517fbbbcb96c8a3','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1612,'clm_6517fbbbcb96c8a3','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1613,'clm_6517fbbbcb96c8a3','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1614,'clm_6517fbbbcb96c8a3','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1615,'clm_6517fbbbcb96c8a3','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1616,'clm_6517fbbbcb96c8a3','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1617,'clm_6517fbbbcb96c8a3','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1618,'clm_6517fbbbcb96c8a3','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1619,'clm_6517fbbbcb96c8a3','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1620,'clm_6517fbbbcb96c8a3','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:06');
INSERT INTO "claim_evidence_links" VALUES(1621,'clm_18ecd60bbb13c668','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1622,'clm_18ecd60bbb13c668','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1623,'clm_18ecd60bbb13c668','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1624,'clm_18ecd60bbb13c668','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1625,'clm_18ecd60bbb13c668','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1626,'clm_18ecd60bbb13c668','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1627,'clm_18ecd60bbb13c668','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1628,'clm_18ecd60bbb13c668','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1629,'clm_18ecd60bbb13c668','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1630,'clm_18ecd60bbb13c668','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1631,'clm_18ecd60bbb13c668','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1632,'clm_18ecd60bbb13c668','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1633,'clm_18ecd60bbb13c668','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1634,'clm_18ecd60bbb13c668','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1635,'clm_18ecd60bbb13c668','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1636,'clm_18ecd60bbb13c668','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1637,'clm_18ecd60bbb13c668','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1638,'clm_18ecd60bbb13c668','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1639,'clm_18ecd60bbb13c668','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1640,'clm_18ecd60bbb13c668','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:07');
INSERT INTO "claim_evidence_links" VALUES(1641,'clm_966b68f88bae2fa4','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1642,'clm_966b68f88bae2fa4','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1643,'clm_966b68f88bae2fa4','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1644,'clm_966b68f88bae2fa4','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1645,'clm_966b68f88bae2fa4','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1646,'clm_966b68f88bae2fa4','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1647,'clm_966b68f88bae2fa4','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1648,'clm_966b68f88bae2fa4','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1649,'clm_966b68f88bae2fa4','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1650,'clm_966b68f88bae2fa4','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1651,'clm_966b68f88bae2fa4','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1652,'clm_966b68f88bae2fa4','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1653,'clm_966b68f88bae2fa4','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1654,'clm_966b68f88bae2fa4','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1655,'clm_966b68f88bae2fa4','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1656,'clm_966b68f88bae2fa4','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1657,'clm_966b68f88bae2fa4','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1658,'clm_966b68f88bae2fa4','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1659,'clm_966b68f88bae2fa4','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1660,'clm_966b68f88bae2fa4','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:08');
INSERT INTO "claim_evidence_links" VALUES(1661,'clm_69f6db0d8675f735','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1662,'clm_69f6db0d8675f735','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1663,'clm_69f6db0d8675f735','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1664,'clm_69f6db0d8675f735','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1665,'clm_69f6db0d8675f735','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1666,'clm_69f6db0d8675f735','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1667,'clm_69f6db0d8675f735','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1668,'clm_69f6db0d8675f735','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1669,'clm_69f6db0d8675f735','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1670,'clm_69f6db0d8675f735','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1671,'clm_69f6db0d8675f735','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1672,'clm_69f6db0d8675f735','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1673,'clm_69f6db0d8675f735','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1674,'clm_69f6db0d8675f735','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1675,'clm_69f6db0d8675f735','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1676,'clm_69f6db0d8675f735','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1677,'clm_69f6db0d8675f735','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1678,'clm_69f6db0d8675f735','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1679,'clm_69f6db0d8675f735','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1680,'clm_69f6db0d8675f735','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:09');
INSERT INTO "claim_evidence_links" VALUES(1681,'clm_a3455f67b3a090aa','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1682,'clm_a3455f67b3a090aa','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1683,'clm_a3455f67b3a090aa','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1684,'clm_a3455f67b3a090aa','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1685,'clm_a3455f67b3a090aa','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1686,'clm_a3455f67b3a090aa','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1687,'clm_a3455f67b3a090aa','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1688,'clm_a3455f67b3a090aa','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1689,'clm_a3455f67b3a090aa','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1690,'clm_a3455f67b3a090aa','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1691,'clm_a3455f67b3a090aa','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1692,'clm_a3455f67b3a090aa','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1693,'clm_a3455f67b3a090aa','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1694,'clm_a3455f67b3a090aa','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1695,'clm_a3455f67b3a090aa','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1696,'clm_a3455f67b3a090aa','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1697,'clm_a3455f67b3a090aa','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1698,'clm_a3455f67b3a090aa','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1699,'clm_a3455f67b3a090aa','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1700,'clm_a3455f67b3a090aa','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:10');
INSERT INTO "claim_evidence_links" VALUES(1701,'clm_e5a5c4e08f614a24','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1702,'clm_e5a5c4e08f614a24','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1703,'clm_e5a5c4e08f614a24','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1704,'clm_e5a5c4e08f614a24','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1705,'clm_e5a5c4e08f614a24','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1706,'clm_e5a5c4e08f614a24','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1707,'clm_e5a5c4e08f614a24','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1708,'clm_e5a5c4e08f614a24','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1709,'clm_e5a5c4e08f614a24','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1710,'clm_e5a5c4e08f614a24','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1711,'clm_e5a5c4e08f614a24','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1712,'clm_e5a5c4e08f614a24','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1713,'clm_e5a5c4e08f614a24','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1714,'clm_e5a5c4e08f614a24','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1715,'clm_e5a5c4e08f614a24','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1716,'clm_e5a5c4e08f614a24','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1717,'clm_e5a5c4e08f614a24','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1718,'clm_e5a5c4e08f614a24','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1719,'clm_e5a5c4e08f614a24','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1720,'clm_e5a5c4e08f614a24','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:11');
INSERT INTO "claim_evidence_links" VALUES(1721,'clm_1e566bba6361356b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1722,'clm_1e566bba6361356b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1723,'clm_1e566bba6361356b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1724,'clm_1e566bba6361356b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1725,'clm_1e566bba6361356b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1726,'clm_1e566bba6361356b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1727,'clm_1e566bba6361356b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1728,'clm_1e566bba6361356b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1729,'clm_1e566bba6361356b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1730,'clm_1e566bba6361356b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1731,'clm_1e566bba6361356b','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1732,'clm_1e566bba6361356b','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1733,'clm_1e566bba6361356b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1734,'clm_1e566bba6361356b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1735,'clm_1e566bba6361356b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1736,'clm_1e566bba6361356b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1737,'clm_1e566bba6361356b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1738,'clm_1e566bba6361356b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1739,'clm_1e566bba6361356b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1740,'clm_1e566bba6361356b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:08:12');
INSERT INTO "claim_evidence_links" VALUES(1741,'clm_8cd46c5da4a38b8b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1742,'clm_8cd46c5da4a38b8b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1743,'clm_8cd46c5da4a38b8b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1744,'clm_8cd46c5da4a38b8b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1745,'clm_8cd46c5da4a38b8b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1746,'clm_8cd46c5da4a38b8b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1747,'clm_8cd46c5da4a38b8b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1748,'clm_8cd46c5da4a38b8b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1749,'clm_8cd46c5da4a38b8b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1750,'clm_8cd46c5da4a38b8b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1751,'clm_8cd46c5da4a38b8b','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1752,'clm_8cd46c5da4a38b8b','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1753,'clm_8cd46c5da4a38b8b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1754,'clm_8cd46c5da4a38b8b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1755,'clm_8cd46c5da4a38b8b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1756,'clm_8cd46c5da4a38b8b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1757,'clm_8cd46c5da4a38b8b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1758,'clm_8cd46c5da4a38b8b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1759,'clm_8cd46c5da4a38b8b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1760,'clm_8cd46c5da4a38b8b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:13:16');
INSERT INTO "claim_evidence_links" VALUES(1761,'clm_3a6c3a9d850ea00a','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1762,'clm_3a6c3a9d850ea00a','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1763,'clm_3a6c3a9d850ea00a','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1764,'clm_3a6c3a9d850ea00a','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1765,'clm_3a6c3a9d850ea00a','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1766,'clm_3a6c3a9d850ea00a','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1767,'clm_3a6c3a9d850ea00a','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1768,'clm_3a6c3a9d850ea00a','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1769,'clm_3a6c3a9d850ea00a','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1770,'clm_3a6c3a9d850ea00a','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1771,'clm_3a6c3a9d850ea00a','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1772,'clm_3a6c3a9d850ea00a','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1773,'clm_3a6c3a9d850ea00a','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1774,'clm_3a6c3a9d850ea00a','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1775,'clm_3a6c3a9d850ea00a','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1776,'clm_3a6c3a9d850ea00a','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1777,'clm_3a6c3a9d850ea00a','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1778,'clm_3a6c3a9d850ea00a','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1779,'clm_3a6c3a9d850ea00a','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1780,'clm_3a6c3a9d850ea00a','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:13:18');
INSERT INTO "claim_evidence_links" VALUES(1781,'clm_6ffefb767f72f8d7','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1782,'clm_6ffefb767f72f8d7','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1783,'clm_6ffefb767f72f8d7','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1784,'clm_6ffefb767f72f8d7','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1785,'clm_6ffefb767f72f8d7','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1786,'clm_6ffefb767f72f8d7','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1787,'clm_6ffefb767f72f8d7','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1788,'clm_6ffefb767f72f8d7','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1789,'clm_6ffefb767f72f8d7','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1790,'clm_6ffefb767f72f8d7','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1791,'clm_6ffefb767f72f8d7','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1792,'clm_6ffefb767f72f8d7','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1793,'clm_6ffefb767f72f8d7','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1794,'clm_6ffefb767f72f8d7','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1795,'clm_6ffefb767f72f8d7','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1796,'clm_6ffefb767f72f8d7','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1797,'clm_6ffefb767f72f8d7','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1798,'clm_6ffefb767f72f8d7','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1799,'clm_6ffefb767f72f8d7','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1800,'clm_6ffefb767f72f8d7','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:14:49');
INSERT INTO "claim_evidence_links" VALUES(1801,'clm_3845b43635d6755b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1802,'clm_3845b43635d6755b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1803,'clm_3845b43635d6755b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1804,'clm_3845b43635d6755b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1805,'clm_3845b43635d6755b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1806,'clm_3845b43635d6755b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1807,'clm_3845b43635d6755b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1808,'clm_3845b43635d6755b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1809,'clm_3845b43635d6755b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1810,'clm_3845b43635d6755b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1811,'clm_3845b43635d6755b','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1812,'clm_3845b43635d6755b','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1813,'clm_3845b43635d6755b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1814,'clm_3845b43635d6755b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1815,'clm_3845b43635d6755b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1816,'clm_3845b43635d6755b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1817,'clm_3845b43635d6755b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1818,'clm_3845b43635d6755b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1819,'clm_3845b43635d6755b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1820,'clm_3845b43635d6755b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:16:24');
INSERT INTO "claim_evidence_links" VALUES(1821,'clm_be969b070889ef5f','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1822,'clm_be969b070889ef5f','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1823,'clm_be969b070889ef5f','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1824,'clm_be969b070889ef5f','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1825,'clm_be969b070889ef5f','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1826,'clm_be969b070889ef5f','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1827,'clm_be969b070889ef5f','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1828,'clm_be969b070889ef5f','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1829,'clm_be969b070889ef5f','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1830,'clm_be969b070889ef5f','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1831,'clm_be969b070889ef5f','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1832,'clm_be969b070889ef5f','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1833,'clm_be969b070889ef5f','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1834,'clm_be969b070889ef5f','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1835,'clm_be969b070889ef5f','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1836,'clm_be969b070889ef5f','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1837,'clm_be969b070889ef5f','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1838,'clm_be969b070889ef5f','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1839,'clm_be969b070889ef5f','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1840,'clm_be969b070889ef5f','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:17:13');
INSERT INTO "claim_evidence_links" VALUES(1841,'clm_36f31a6d2150247e','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1842,'clm_36f31a6d2150247e','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1843,'clm_36f31a6d2150247e','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1844,'clm_36f31a6d2150247e','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1845,'clm_36f31a6d2150247e','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1846,'clm_36f31a6d2150247e','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1847,'clm_36f31a6d2150247e','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1848,'clm_36f31a6d2150247e','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1849,'clm_36f31a6d2150247e','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1850,'clm_36f31a6d2150247e','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1851,'clm_36f31a6d2150247e','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1852,'clm_36f31a6d2150247e','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1853,'clm_36f31a6d2150247e','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1854,'clm_36f31a6d2150247e','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1855,'clm_36f31a6d2150247e','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1856,'clm_36f31a6d2150247e','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1857,'clm_36f31a6d2150247e','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1858,'clm_36f31a6d2150247e','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1859,'clm_36f31a6d2150247e','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1860,'clm_36f31a6d2150247e','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:17:30');
INSERT INTO "claim_evidence_links" VALUES(1861,'clm_35acb77b26dd56ba','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1862,'clm_35acb77b26dd56ba','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1863,'clm_35acb77b26dd56ba','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1864,'clm_35acb77b26dd56ba','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1865,'clm_35acb77b26dd56ba','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1866,'clm_35acb77b26dd56ba','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1867,'clm_35acb77b26dd56ba','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1868,'clm_35acb77b26dd56ba','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1869,'clm_35acb77b26dd56ba','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1870,'clm_35acb77b26dd56ba','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1871,'clm_35acb77b26dd56ba','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1872,'clm_35acb77b26dd56ba','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1873,'clm_35acb77b26dd56ba','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1874,'clm_35acb77b26dd56ba','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1875,'clm_35acb77b26dd56ba','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1876,'clm_35acb77b26dd56ba','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1877,'clm_35acb77b26dd56ba','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1878,'clm_35acb77b26dd56ba','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1879,'clm_35acb77b26dd56ba','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1880,'clm_35acb77b26dd56ba','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:17:37');
INSERT INTO "claim_evidence_links" VALUES(1881,'clm_e092ad27dd245df4','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1882,'clm_e092ad27dd245df4','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1883,'clm_e092ad27dd245df4','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1884,'clm_e092ad27dd245df4','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1885,'clm_e092ad27dd245df4','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1886,'clm_e092ad27dd245df4','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1887,'clm_e092ad27dd245df4','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1888,'clm_e092ad27dd245df4','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1889,'clm_e092ad27dd245df4','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1890,'clm_e092ad27dd245df4','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1891,'clm_e092ad27dd245df4','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1892,'clm_e092ad27dd245df4','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1893,'clm_e092ad27dd245df4','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1894,'clm_e092ad27dd245df4','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1895,'clm_e092ad27dd245df4','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1896,'clm_e092ad27dd245df4','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1897,'clm_e092ad27dd245df4','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1898,'clm_e092ad27dd245df4','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1899,'clm_e092ad27dd245df4','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1900,'clm_e092ad27dd245df4','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:18:48');
INSERT INTO "claim_evidence_links" VALUES(1901,'clm_e466353733e74c19','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1902,'clm_e466353733e74c19','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1903,'clm_e466353733e74c19','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1904,'clm_e466353733e74c19','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1905,'clm_e466353733e74c19','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1906,'clm_e466353733e74c19','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1907,'clm_e466353733e74c19','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1908,'clm_e466353733e74c19','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1909,'clm_e466353733e74c19','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1910,'clm_e466353733e74c19','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1911,'clm_e466353733e74c19','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1912,'clm_e466353733e74c19','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1913,'clm_e466353733e74c19','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1914,'clm_e466353733e74c19','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1915,'clm_e466353733e74c19','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1916,'clm_e466353733e74c19','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1917,'clm_e466353733e74c19','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1918,'clm_e466353733e74c19','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1919,'clm_e466353733e74c19','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1920,'clm_e466353733e74c19','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:20:21');
INSERT INTO "claim_evidence_links" VALUES(1921,'clm_fa29a161560e9ed7','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1922,'clm_fa29a161560e9ed7','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1923,'clm_fa29a161560e9ed7','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1924,'clm_fa29a161560e9ed7','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1925,'clm_fa29a161560e9ed7','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1926,'clm_fa29a161560e9ed7','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1927,'clm_fa29a161560e9ed7','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1928,'clm_fa29a161560e9ed7','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1929,'clm_fa29a161560e9ed7','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1930,'clm_fa29a161560e9ed7','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1931,'clm_fa29a161560e9ed7','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1932,'clm_fa29a161560e9ed7','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1933,'clm_fa29a161560e9ed7','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1934,'clm_fa29a161560e9ed7','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1935,'clm_fa29a161560e9ed7','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1936,'clm_fa29a161560e9ed7','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1937,'clm_fa29a161560e9ed7','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1938,'clm_fa29a161560e9ed7','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1939,'clm_fa29a161560e9ed7','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1940,'clm_fa29a161560e9ed7','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:21:55');
INSERT INTO "claim_evidence_links" VALUES(1941,'clm_15935d41c4e4d75d','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1942,'clm_15935d41c4e4d75d','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1943,'clm_15935d41c4e4d75d','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1944,'clm_15935d41c4e4d75d','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1945,'clm_15935d41c4e4d75d','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1946,'clm_15935d41c4e4d75d','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1947,'clm_15935d41c4e4d75d','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1948,'clm_15935d41c4e4d75d','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1949,'clm_15935d41c4e4d75d','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1950,'clm_15935d41c4e4d75d','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1951,'clm_15935d41c4e4d75d','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1952,'clm_15935d41c4e4d75d','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1953,'clm_15935d41c4e4d75d','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1954,'clm_15935d41c4e4d75d','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1955,'clm_15935d41c4e4d75d','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1956,'clm_15935d41c4e4d75d','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1957,'clm_15935d41c4e4d75d','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1958,'clm_15935d41c4e4d75d','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1959,'clm_15935d41c4e4d75d','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1960,'clm_15935d41c4e4d75d','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:23:28');
INSERT INTO "claim_evidence_links" VALUES(1961,'clm_11484381aa978e82','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1962,'clm_11484381aa978e82','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1963,'clm_11484381aa978e82','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1964,'clm_11484381aa978e82','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1965,'clm_11484381aa978e82','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1966,'clm_11484381aa978e82','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1967,'clm_11484381aa978e82','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1968,'clm_11484381aa978e82','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1969,'clm_11484381aa978e82','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1970,'clm_11484381aa978e82','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1971,'clm_11484381aa978e82','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1972,'clm_11484381aa978e82','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1973,'clm_11484381aa978e82','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1974,'clm_11484381aa978e82','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1975,'clm_11484381aa978e82','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1976,'clm_11484381aa978e82','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1977,'clm_11484381aa978e82','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1978,'clm_11484381aa978e82','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1979,'clm_11484381aa978e82','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1980,'clm_11484381aa978e82','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:25:01');
INSERT INTO "claim_evidence_links" VALUES(1981,'clm_340ee0d6f2ca5ab0','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1982,'clm_340ee0d6f2ca5ab0','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1983,'clm_340ee0d6f2ca5ab0','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1984,'clm_340ee0d6f2ca5ab0','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1985,'clm_340ee0d6f2ca5ab0','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1986,'clm_340ee0d6f2ca5ab0','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1987,'clm_340ee0d6f2ca5ab0','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1988,'clm_340ee0d6f2ca5ab0','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1989,'clm_340ee0d6f2ca5ab0','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1990,'clm_340ee0d6f2ca5ab0','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1991,'clm_340ee0d6f2ca5ab0','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1992,'clm_340ee0d6f2ca5ab0','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1993,'clm_340ee0d6f2ca5ab0','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1994,'clm_340ee0d6f2ca5ab0','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1995,'clm_340ee0d6f2ca5ab0','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1996,'clm_340ee0d6f2ca5ab0','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1997,'clm_340ee0d6f2ca5ab0','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1998,'clm_340ee0d6f2ca5ab0','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(1999,'clm_340ee0d6f2ca5ab0','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(2000,'clm_340ee0d6f2ca5ab0','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:26:36');
INSERT INTO "claim_evidence_links" VALUES(2001,'clm_3ec0fd56fd51667b','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2002,'clm_3ec0fd56fd51667b','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2003,'clm_3ec0fd56fd51667b','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2004,'clm_3ec0fd56fd51667b','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2005,'clm_3ec0fd56fd51667b','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2006,'clm_3ec0fd56fd51667b','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2007,'clm_3ec0fd56fd51667b','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2008,'clm_3ec0fd56fd51667b','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2009,'clm_3ec0fd56fd51667b','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2010,'clm_3ec0fd56fd51667b','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2011,'clm_3ec0fd56fd51667b','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2012,'clm_3ec0fd56fd51667b','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2013,'clm_3ec0fd56fd51667b','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2014,'clm_3ec0fd56fd51667b','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2015,'clm_3ec0fd56fd51667b','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2016,'clm_3ec0fd56fd51667b','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2017,'clm_3ec0fd56fd51667b','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2018,'clm_3ec0fd56fd51667b','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2019,'clm_3ec0fd56fd51667b','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2020,'clm_3ec0fd56fd51667b','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:29:22');
INSERT INTO "claim_evidence_links" VALUES(2021,'clm_20860d13deca9cb6','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2022,'clm_20860d13deca9cb6','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2023,'clm_20860d13deca9cb6','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2024,'clm_20860d13deca9cb6','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2025,'clm_20860d13deca9cb6','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2026,'clm_20860d13deca9cb6','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2027,'clm_20860d13deca9cb6','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2028,'clm_20860d13deca9cb6','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2029,'clm_20860d13deca9cb6','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2030,'clm_20860d13deca9cb6','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2031,'clm_20860d13deca9cb6','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2032,'clm_20860d13deca9cb6','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2033,'clm_20860d13deca9cb6','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2034,'clm_20860d13deca9cb6','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2035,'clm_20860d13deca9cb6','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2036,'clm_20860d13deca9cb6','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2037,'clm_20860d13deca9cb6','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2038,'clm_20860d13deca9cb6','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2039,'clm_20860d13deca9cb6','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2040,'clm_20860d13deca9cb6','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:29:23');
INSERT INTO "claim_evidence_links" VALUES(2041,'clm_7195ccea7101fa52','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2042,'clm_7195ccea7101fa52','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2043,'clm_7195ccea7101fa52','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2044,'clm_7195ccea7101fa52','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2045,'clm_7195ccea7101fa52','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2046,'clm_7195ccea7101fa52','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2047,'clm_7195ccea7101fa52','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2048,'clm_7195ccea7101fa52','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2049,'clm_7195ccea7101fa52','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2050,'clm_7195ccea7101fa52','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2051,'clm_7195ccea7101fa52','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2052,'clm_7195ccea7101fa52','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2053,'clm_7195ccea7101fa52','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2054,'clm_7195ccea7101fa52','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2055,'clm_7195ccea7101fa52','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2056,'clm_7195ccea7101fa52','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2057,'clm_7195ccea7101fa52','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2058,'clm_7195ccea7101fa52','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2059,'clm_7195ccea7101fa52','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2060,'clm_7195ccea7101fa52','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:30:55');
INSERT INTO "claim_evidence_links" VALUES(2061,'clm_8047274bef0c5f78','ev_fin_02599521cdbed155','supports',0,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2062,'clm_8047274bef0c5f78','ev_fin_cb87c26679d370cf','supports',1,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2063,'clm_8047274bef0c5f78','ev_fin_76eee8e02ca574b1','supports',2,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2064,'clm_8047274bef0c5f78','ev_fin_3c745ad607cf9e50','supports',3,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2065,'clm_8047274bef0c5f78','ev_fin_d6a0bdb069599c9c','supports',4,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2066,'clm_8047274bef0c5f78','ev_fin_a155539ae3d92cde','supports',5,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2067,'clm_8047274bef0c5f78','ev_fin_8dbd9d630dbd2f79','supports',6,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2068,'clm_8047274bef0c5f78','ev_fin_f614f09c260d40e1','supports',7,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2069,'clm_8047274bef0c5f78','ev_fin_58ab6a18a2751d61','supports',8,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2070,'clm_8047274bef0c5f78','ev_fin_f1547d94b1873ff7','supports',9,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2071,'clm_8047274bef0c5f78','ev_fin_633671310de9326b','supports',10,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2072,'clm_8047274bef0c5f78','ev_fin_464910c137146f73','supports',11,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2073,'clm_8047274bef0c5f78','ev_fin_7c2b0d31dc5b83b1','supports',12,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2074,'clm_8047274bef0c5f78','ev_fin_1ee5c03a14ef00bd','supports',13,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2075,'clm_8047274bef0c5f78','ev_fin_336d435f61d20911','supports',14,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2076,'clm_8047274bef0c5f78','ev_fin_da76edc055c14e3d','supports',15,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2077,'clm_8047274bef0c5f78','ev_fin_114c390fed1c8e82','supports',16,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2078,'clm_8047274bef0c5f78','ev_fin_7c9122e027c7ebd2','supports',17,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2079,'clm_8047274bef0c5f78','ev_fin_2eade9b9db42792f','supports',18,'2026-08-25 10:32:28');
INSERT INTO "claim_evidence_links" VALUES(2080,'clm_8047274bef0c5f78','ev_fin_527265ff7a238e2a','supports',19,'2026-08-25 10:32:28');
CREATE TABLE claims (
	claim_id VARCHAR(64) NOT NULL, 
	turn_id VARCHAR(64), 
	text TEXT NOT NULL, 
	claim_type VARCHAR(32), 
	severity VARCHAR(16) NOT NULL, 
	confidence FLOAT, 
	rule_id VARCHAR(64), 
	rule_version VARCHAR(32), 
	verification_status VARCHAR(16) NOT NULL, 
	limitations JSON, 
	generated_at DATETIME NOT NULL, 
	trace_id VARCHAR(64), 
	company_code VARCHAR(32), 
	module VARCHAR(32), 
	PRIMARY KEY (claim_id)
);
INSERT INTO "claims" VALUES('clm_ce29e78b61145097','9ec12fe1-377e-400c-8c22-eb752be222c4','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_312cf5857b319f60','751aed16-964f-4a98-9773-6135aa21988f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:50:59','751aed16-964f-4a98-9773-6135aa21988f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_5203faf1a460d67d','cd2203a4-f5a2-487c-9e4e-7d8e9fcc487a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:52:12','cd2203a4-f5a2-487c-9e4e-7d8e9fcc487a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_5e7dd9547af6b615','7aaa06ce-089d-42a4-b082-4d76012e4f67','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:53:46','7aaa06ce-089d-42a4-b082-4d76012e4f67','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_73a0fccd9a2344b3','d4a7713a-6868-4273-9017-b1d2de156b2d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:55:19','d4a7713a-6868-4273-9017-b1d2de156b2d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_496dd22e7b3f2642','9ca4f5c5-77c3-463a-83d3-6ed343ed2a50','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:56:52','9ca4f5c5-77c3-463a-83d3-6ed343ed2a50','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_70c6d21c432c941d','e4708a2b-7f5e-4b0d-b686-4cae268f4b4f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:58:25','e4708a2b-7f5e-4b0d-b686-4cae268f4b4f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c9bba44592553590','1a66a9d0-5e61-40a8-91f6-76b623024519','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 06:59:58','1a66a9d0-5e61-40a8-91f6-76b623024519','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_82b7ca7d48ed8d10','9ab31516-1137-48eb-b1a5-e77e7b8a2b22','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:01:32','9ab31516-1137-48eb-b1a5-e77e7b8a2b22','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_92ccbbbd9b24f232','31a6d83d-e455-4b97-9db2-59d8664f813f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:03:05','31a6d83d-e455-4b97-9db2-59d8664f813f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_4de9f9ae0b05ae9a','e78cb7d9-f9bd-40da-bbef-5b0c13f4ae28','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:04:33','e78cb7d9-f9bd-40da-bbef-5b0c13f4ae28','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_1e53346483557075','6b99caf9-78a7-40cc-b94e-1a61a426be7f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:04:34','6b99caf9-78a7-40cc-b94e-1a61a426be7f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c793f4839cb58a97','64d7e594-52a9-4bed-939b-d405d4952fa1','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:04:38','64d7e594-52a9-4bed-939b-d405d4952fa1','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_3e83783bbb448523','d1d27c34-6dbf-4803-9263-00cfc6fab592','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:04:39','d1d27c34-6dbf-4803-9263-00cfc6fab592','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_6d8898c9e6e15763','0a96abf9-b323-4068-83c4-9ca9306896a1','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:04:41','0a96abf9-b323-4068-83c4-9ca9306896a1','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_a06c9a7a6031b347','495ea06c-30cc-45ee-9544-cdd4452b2519','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:06:12','495ea06c-30cc-45ee-9544-cdd4452b2519','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_2644daa027b31de8','5f6f7555-d09d-4018-9296-59807b1a7506','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:07:23','5f6f7555-d09d-4018-9296-59807b1a7506','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_f543045b19087ad7','d4f2ba16-20f1-4d4b-84ed-8daca9ca05dd','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:09:03','d4f2ba16-20f1-4d4b-84ed-8daca9ca05dd','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_500f2757ecd1fda4','680b32f7-dcfb-4fb1-847f-9fed8ddfa6e8','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:09:40','680b32f7-dcfb-4fb1-847f-9fed8ddfa6e8','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c6a9dec76bf2d22e','48f566ce-d59c-4b66-9e03-6da4adada761','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:11:14','48f566ce-d59c-4b66-9e03-6da4adada761','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_ff99955718e00bf8','7290729b-69a0-4cde-b518-920f48c847e6','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:12:52','7290729b-69a0-4cde-b518-920f48c847e6','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_6e5b5a2cd5a834f7','350adb2f-e2bb-4313-a78e-d4469f3fb648','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:14:25','350adb2f-e2bb-4313-a78e-d4469f3fb648','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_a77c03f6dcf9dc86','c097816b-bfbf-45ce-9794-c7a74d266b75','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:15:58','c097816b-bfbf-45ce-9794-c7a74d266b75','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_103e953fedb1dd8c','8d7bbbd7-d789-4609-a093-8385ada90c21','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:17:31','8d7bbbd7-d789-4609-a093-8385ada90c21','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_8774625f24d3416f','c9275605-0cf2-45a0-a2cf-77d25c60fa3e','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:19:04','c9275605-0cf2-45a0-a2cf-77d25c60fa3e','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c4c8bae84e288fa1','6d015c87-6202-4311-80f7-19ab01907317','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:20:38','6d015c87-6202-4311-80f7-19ab01907317','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_72d2602d31516918','88d67924-3888-4e2a-bc09-4894f2ecabf0','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:22:11','88d67924-3888-4e2a-bc09-4894f2ecabf0','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_88b8e547f3f7de81','8274683d-6dc8-44ce-9dd7-3de38f4835a3','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:25:18','8274683d-6dc8-44ce-9dd7-3de38f4835a3','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_b0460fca3c6479fb','d1ee1b4f-9d2d-41d6-827a-37f924087adf','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:26:51','d1ee1b4f-9d2d-41d6-827a-37f924087adf','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_558509067c49622e','97279f9f-1e78-48b5-a45f-900c1b30bc3a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:31:03','97279f9f-1e78-48b5-a45f-900c1b30bc3a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_728d15106d1b7001','e962b6d0-10b0-43dc-8d46-98e3a148f3c2','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:32:18','e962b6d0-10b0-43dc-8d46-98e3a148f3c2','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_2b0d4fadee94681b','857e7523-3519-4ddd-93ee-5ad2b09c35aa','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:33:51','857e7523-3519-4ddd-93ee-5ad2b09c35aa','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_ee606d3716588b44','4df64d36-5a44-4faa-b3b6-e0cbd6cdb0ed','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:34:29','4df64d36-5a44-4faa-b3b6-e0cbd6cdb0ed','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_74e2c971f83ea1e9','98a3ac9e-a382-423f-8397-5272260408b7','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:36:12','98a3ac9e-a382-423f-8397-5272260408b7','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_9f742176be79612b','651e01ae-7259-4c03-b66f-431fab81511a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:36:36','651e01ae-7259-4c03-b66f-431fab81511a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_efd69c82742a70f0','4361dd96-b821-4cc2-9564-ab885fd85649','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:37:24','4361dd96-b821-4cc2-9564-ab885fd85649','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_59dcd9fc72b40e89','0575c83d-ff1b-492b-8ef0-66c0e35fca24','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 07:38:57','0575c83d-ff1b-492b-8ef0-66c0e35fca24','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_fe9455d62a5e3ec9','10be80db-2c1c-47de-a2ae-7c34da43e2ac','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:29:27','10be80db-2c1c-47de-a2ae-7c34da43e2ac','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_3f9cdb7a8d1419e1','3a1e518d-f593-43f1-aac0-5b1a66ed451f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:30:40','3a1e518d-f593-43f1-aac0-5b1a66ed451f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_57dd37f32d881858','1734a03c-63da-44bc-b9dc-f90fdd79ee68','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:31:24','1734a03c-63da-44bc-b9dc-f90fdd79ee68','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_83b85d44589ff246','5ae574a8-901d-47f9-ba99-eb856a6eb4ba','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:31:26','5ae574a8-901d-47f9-ba99-eb856a6eb4ba','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_5a7ade3b1327e1a9','f74c4d1b-1487-483b-9a6e-cdc032ea6455','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:31:27','f74c4d1b-1487-483b-9a6e-cdc032ea6455','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_b8f6e7db9bed54c9','b93de4ee-a850-4c8d-80c1-934cf1193eef','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:31:34','b93de4ee-a850-4c8d-80c1-934cf1193eef','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_32ece868a6c4d78e','ca5efde3-966f-4799-8f2c-ea9a9a77967a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:32:58','ca5efde3-966f-4799-8f2c-ea9a9a77967a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c395b3088f333cb9','71ed0758-093a-446d-aab2-f4cb28430845','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:33:09','71ed0758-093a-446d-aab2-f4cb28430845','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_72c09be7538b5cd8','05f08b1a-8261-47c6-868b-ba61c11dcb4e','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:34:31','05f08b1a-8261-47c6-868b-ba61c11dcb4e','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_cbfba9b476448c60','3696af77-2fd9-4654-b3c8-2ccaeecc85f0','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:34:42','3696af77-2fd9-4654-b3c8-2ccaeecc85f0','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_06224b62d16ebb93','33e0dc83-0b5f-4d26-abc1-5198a12150be','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:36:05','33e0dc83-0b5f-4d26-abc1-5198a12150be','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_aa6f82ad2d3327d7','96417a07-93f9-49db-a4aa-fa6ea457e1ce','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:36:15','96417a07-93f9-49db-a4aa-fa6ea457e1ce','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_ccb41ceae53614ec','4dad10ad-a0d0-4135-a865-f516ef0c2f2c','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:37:21','4dad10ad-a0d0-4135-a865-f516ef0c2f2c','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_9e0bdb0fbca816bd','0290fc7c-1409-47cc-98aa-a4608b15680c','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:37:27','0290fc7c-1409-47cc-98aa-a4608b15680c','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_99408cedf61ab1be','5fc13864-b81e-4366-bb37-cafdf46b18b9','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:37:32','5fc13864-b81e-4366-bb37-cafdf46b18b9','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e22b0c978e351169','5722c359-c455-4332-95e9-197643a6bac4','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:37:38','5722c359-c455-4332-95e9-197643a6bac4','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_9706ec36fc7a92de','75f79c87-5279-42e1-8443-6512ec9ce7c9','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:37:48','75f79c87-5279-42e1-8443-6512ec9ce7c9','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_7301fc3ea57db886','2404500c-55fb-46ef-83ed-513e2895068d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:39:11','2404500c-55fb-46ef-83ed-513e2895068d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_8e837a51f94e76b5','6647dba4-8b7e-440e-b24d-f2526daea4fe','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:39:21','6647dba4-8b7e-440e-b24d-f2526daea4fe','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_77ce8716d19a4745','d21a6c96-da64-491f-9fbe-1750cc98e3f5','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:39:53','d21a6c96-da64-491f-9fbe-1750cc98e3f5','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c0fe0787b99bd861','b2f4f5f0-0946-40ed-8aaa-cfbd627e0fb0','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:41:28','b2f4f5f0-0946-40ed-8aaa-cfbd627e0fb0','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_451d15cec2615e80','7cb15ab5-80f8-4f5c-9b4e-aed8aaa52c27','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:43:00','7cb15ab5-80f8-4f5c-9b4e-aed8aaa52c27','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_c200a59f876e1e58','dbc5cdf9-0fb1-4f29-bf03-99592d8e048a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:44:33','dbc5cdf9-0fb1-4f29-bf03-99592d8e048a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_1d1b8907ed55f552','dae56990-4fc5-4b43-98a0-c8194ddf1640','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:46:06','dae56990-4fc5-4b43-98a0-c8194ddf1640','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_538889b54c6036aa','17fc6932-416c-4363-9a10-8859436688dc','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:47:42','17fc6932-416c-4363-9a10-8859436688dc','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_a20f3597c49dfe79','8b8fb8b8-a10e-4e2f-9ed5-8f9d25b2bbd6','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:49:17','8b8fb8b8-a10e-4e2f-9ed5-8f9d25b2bbd6','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_0f9ceecbc94033fb','431696f9-44f9-4662-bfe6-91aa7365e3f3','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:50:39','431696f9-44f9-4662-bfe6-91aa7365e3f3','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_6ea20263b9d3f7e6','242a48c8-40c7-4521-9c38-70500fb595a9','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:52:12','242a48c8-40c7-4521-9c38-70500fb595a9','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_dab6deb6bd805a30','b7e7066d-87c1-4bba-affe-32c1d814ba6e','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:53:45','b7e7066d-87c1-4bba-affe-32c1d814ba6e','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_81218d250f701a33','2735a5eb-f4f3-4ab3-ab87-948be2c82d4c','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:55:19','2735a5eb-f4f3-4ab3-ab87-948be2c82d4c','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_98e312df1f670dcd','5db78998-edf5-489b-bda5-2fe50032086c','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:56:52','5db78998-edf5-489b-bda5-2fe50032086c','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_a715a3d3da6f0462','2cae3334-2256-4cca-a731-5aac976f8cc0','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:58:25','2cae3334-2256-4cca-a731-5aac976f8cc0','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e9108af353a1ba19','d4eb8907-7e7f-4ef3-9377-f02feab53137','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 09:59:59','d4eb8907-7e7f-4ef3-9377-f02feab53137','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_123202cd3d207010','1b3159d1-ece0-4f78-86fc-20188a5b8955','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:01:11','1b3159d1-ece0-4f78-86fc-20188a5b8955','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_1e9448916689c433','0c6de9f5-72f3-493f-a7b1-e05ec1532d65','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:02:44','0c6de9f5-72f3-493f-a7b1-e05ec1532d65','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_7eac4f776722e850','0d9142b5-a062-4268-86cb-762585bebe91','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:04:17','0d9142b5-a062-4268-86cb-762585bebe91','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_ab2a6cadc513cd00','966e430e-5d64-4439-ae2e-ebb7947410b7','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:06:21','966e430e-5d64-4439-ae2e-ebb7947410b7','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_04bb9e82c61e7f2f','aa230743-eb8f-458f-b907-55e0ff405cd4','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:06:24','aa230743-eb8f-458f-b907-55e0ff405cd4','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_52e555c7b5d9929c','d36d3624-b0e6-44b3-b527-6a284a37644a','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:06:26','d36d3624-b0e6-44b3-b527-6a284a37644a','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_b7de51a2aca9b1d4','040a8293-0f2b-443e-99dc-49dde3f07894','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:07:54','040a8293-0f2b-443e-99dc-49dde3f07894','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e6234d16d3fffffe','351be3ae-d864-4ca9-8311-10885d1b26e4','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:03','351be3ae-d864-4ca9-8311-10885d1b26e4','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_b88bd007c1ec8270','983413fb-b275-4bb8-a028-49fb09fdc72f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:04','983413fb-b275-4bb8-a028-49fb09fdc72f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_d724964db326bb65','9dbc200b-31e3-4828-8663-64ababc4883d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:05','9dbc200b-31e3-4828-8663-64ababc4883d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_6517fbbbcb96c8a3','b2cd4b59-34ca-4e9c-ad95-52b73eb6503f','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:06','b2cd4b59-34ca-4e9c-ad95-52b73eb6503f','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_18ecd60bbb13c668','3ec47006-a493-446c-925f-48b8c50e00da','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:07','3ec47006-a493-446c-925f-48b8c50e00da','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_966b68f88bae2fa4','5a517fae-d1d0-4f57-acab-12567b2c172c','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:08','5a517fae-d1d0-4f57-acab-12567b2c172c','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_69f6db0d8675f735','c9757573-9da3-4e25-b949-43b27871813b','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:09','c9757573-9da3-4e25-b949-43b27871813b','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_a3455f67b3a090aa','042bdeb5-b568-4923-9395-9d1fab1c4f66','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:10','042bdeb5-b568-4923-9395-9d1fab1c4f66','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e5a5c4e08f614a24','4d788877-7e4e-4f54-b32d-d84d101555d2','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:11','4d788877-7e4e-4f54-b32d-d84d101555d2','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_1e566bba6361356b','cd5ca9ea-e605-4975-adee-6e8c8ffcf391','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:08:12','cd5ca9ea-e605-4975-adee-6e8c8ffcf391','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_8cd46c5da4a38b8b','e8f1a059-087e-46bf-9276-8e179752069d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:13:16','e8f1a059-087e-46bf-9276-8e179752069d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_3a6c3a9d850ea00a','c391421a-1f50-4e24-a4da-a8814986492d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:13:18','c391421a-1f50-4e24-a4da-a8814986492d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_6ffefb767f72f8d7','88799bff-6729-48e2-9621-5efa441427b3','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:14:49','88799bff-6729-48e2-9621-5efa441427b3','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_3845b43635d6755b','93e64734-cd1d-4ea2-a78b-b4cb730cda61','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:16:24','93e64734-cd1d-4ea2-a78b-b4cb730cda61','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_be969b070889ef5f','39f4ca6a-df89-4219-b3cb-530af3e17420','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:17:13','39f4ca6a-df89-4219-b3cb-530af3e17420','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_36f31a6d2150247e','95bb1653-f8ba-478d-a2e3-1a2627a4ebf1','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:17:30','95bb1653-f8ba-478d-a2e3-1a2627a4ebf1','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_35acb77b26dd56ba','e39be5d6-aa4c-412e-90b5-2b865c51ef62','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:17:37','e39be5d6-aa4c-412e-90b5-2b865c51ef62','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e092ad27dd245df4','435bd4f6-f9a4-4201-8f5f-64d0050f5b3e','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:18:48','435bd4f6-f9a4-4201-8f5f-64d0050f5b3e','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_e466353733e74c19','c363296c-ac46-418b-80c2-04b96ca8afbb','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:20:21','c363296c-ac46-418b-80c2-04b96ca8afbb','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_fa29a161560e9ed7','eb9ebe93-e2a3-41b0-bb9f-fc0fd49bd868','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:21:55','eb9ebe93-e2a3-41b0-bb9f-fc0fd49bd868','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_15935d41c4e4d75d','76ac4206-6852-441e-b341-9ac2ff02696d','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:23:28','76ac4206-6852-441e-b341-9ac2ff02696d','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_11484381aa978e82','d103a245-d200-4ded-98ca-694781310cac','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:25:01','d103a245-d200-4ded-98ca-694781310cac','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_340ee0d6f2ca5ab0','0f843671-fe51-4a21-b283-a1d2a4e65897','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:26:36','0f843671-fe51-4a21-b283-a1d2a4e65897','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_3ec0fd56fd51667b','f6f63b1b-a141-489e-856e-39fc70702e76','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:29:22','f6f63b1b-a141-489e-856e-39fc70702e76','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_20860d13deca9cb6','7ffbfd13-4dc7-4d97-877f-88b0a850bc98','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:29:23','7ffbfd13-4dc7-4d97-877f-88b0a850bc98','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_7195ccea7101fa52','fd1d89e4-2d78-4b01-98d5-8d3697601222','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:30:55','fd1d89e4-2d78-4b01-98d5-8d3697601222','600518.SH','finance');
INSERT INTO "claims" VALUES('clm_8047274bef0c5f78','9ec2ddfb-2f6b-471d-acc5-495a90dc93f4','毛利率/费用率异常触发（yellow）：毛利率/费用率较历史均值有所偏离，建议持续关注。','risk_signal','yellow',0.7,'R5','finance-rules-1.0.0','verified',NULL,'2026-08-25 10:32:28','9ec2ddfb-2f6b-471d-acc5-495a90dc93f4','600518.SH','finance');
CREATE TABLE companies (
	entity_id VARCHAR(64) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	sec_name VARCHAR(128) NOT NULL, 
	aliases JSON, 
	exchange_code VARCHAR(16), 
	industry_l1 VARCHAR(64), 
	industry_l2 VARCHAR(64), 
	sw_indu_code VARCHAR(32), 
	comp_type_code SMALLINT, 
	listing_date DATE, 
	industry_source VARCHAR(64), 
	industry_as_of DATE, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (entity_id)
);
INSERT INTO "companies" VALUES('company_600518_SH','600518.SH','康美药业股份有限公司','["\u5eb7\u7f8e\u836f\u4e1a", "\u5eb7\u7f8e", "Kangmei Pharmaceutical"]','XSHG','医药生物','中药','370101',1,'2001-03-19','申万研究所','2024-01-01','kmfy_company','scripts/load_kangmei_fixture.py',NULL,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.927914','2026-08-25 08:44:45.927919','null',NULL);
CREATE TABLE conversation_sessions (
	session_id VARCHAR(64) NOT NULL, 
	user_id VARCHAR(64), 
	title VARCHAR(256), 
	status VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	metadata JSON, 
	PRIMARY KEY (session_id)
);
CREATE TABLE conversation_turns (
	turn_id VARCHAR(64) NOT NULL, 
	session_id VARCHAR(64) NOT NULL, 
	turn_index INTEGER NOT NULL, 
	question TEXT NOT NULL, 
	answer TEXT, 
	company_code VARCHAR(32), 
	summary TEXT, 
	trace_id VARCHAR(64), 
	module_status JSON, 
	panel_data JSON, 
	response_meta JSON, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (turn_id), 
	FOREIGN KEY(session_id) REFERENCES conversation_sessions (session_id) ON DELETE CASCADE
);
CREATE TABLE event_cluster_sources (
	id INTEGER NOT NULL, 
	event_cluster_id VARCHAR(64) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	source_record_id VARCHAR(256) NOT NULL, 
	evidence_id VARCHAR(64), 
	source_title VARCHAR(512), 
	source_uri VARCHAR(1024), 
	published_at DATE, 
	content_hash VARCHAR(128), 
	sequence_no INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_event_cluster_source UNIQUE (event_cluster_id, source_record_id), 
	FOREIGN KEY(event_cluster_id) REFERENCES event_clusters (event_cluster_id) ON DELETE CASCADE
);
INSERT INTO "event_cluster_sources" VALUES(13,'evtcl_km_001','news','evtcl_km_001_src0','evtcl_km_001_ev0','财新网：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/0','2018-10-16','hash_evtcl_km_001_0',0);
INSERT INTO "event_cluster_sources" VALUES(14,'evtcl_km_001','news','evtcl_km_001_src1','evtcl_km_001_ev1','证券时报：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/1','2018-10-16','hash_evtcl_km_001_1',1);
INSERT INTO "event_cluster_sources" VALUES(15,'evtcl_km_001','news','evtcl_km_001_src2','evtcl_km_001_ev2','上海证券报：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/2','2018-10-16','hash_evtcl_km_001_2',2);
INSERT INTO "event_cluster_sources" VALUES(16,'evtcl_km_001','news','evtcl_km_001_src3','evtcl_km_001_ev3','第一财经：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/3','2018-10-16','hash_evtcl_km_001_3',3);
INSERT INTO "event_cluster_sources" VALUES(17,'evtcl_km_001','news','evtcl_km_001_src4','evtcl_km_001_ev4','21世纪经济报道：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/4','2018-10-16','hash_evtcl_km_001_4',4);
INSERT INTO "event_cluster_sources" VALUES(18,'evtcl_km_001','news','evtcl_km_001_src5','evtcl_km_001_ev5','中国基金报：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/5','2018-10-16','hash_evtcl_km_001_5',5);
INSERT INTO "event_cluster_sources" VALUES(19,'evtcl_km_001','news','evtcl_km_001_src6','evtcl_km_001_ev6','每日经济新闻：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/6','2018-10-16','hash_evtcl_km_001_6',6);
INSERT INTO "event_cluster_sources" VALUES(20,'evtcl_km_001','news','evtcl_km_001_src7','evtcl_km_001_ev7','新京报：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/7','2018-10-16','hash_evtcl_km_001_7',7);
INSERT INTO "event_cluster_sources" VALUES(21,'evtcl_km_001','news','evtcl_km_001_src8','evtcl_km_001_ev8','界面新闻：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/8','2018-10-16','hash_evtcl_km_001_8',8);
INSERT INTO "event_cluster_sources" VALUES(22,'evtcl_km_001','news','evtcl_km_001_src9','evtcl_km_001_ev9','澎湃新闻：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/9','2018-10-16','hash_evtcl_km_001_9',9);
INSERT INTO "event_cluster_sources" VALUES(23,'evtcl_km_001','news','evtcl_km_001_src10','evtcl_km_001_ev10','华尔街见闻：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/10','2018-10-16','hash_evtcl_km_001_10',10);
INSERT INTO "event_cluster_sources" VALUES(24,'evtcl_km_001','news','evtcl_km_001_src11','evtcl_km_001_ev11','证券市场周刊：存货异常质疑相关报道','https://demo.truthnet.local/kangmei/evtcl_km_001/11','2018-10-16','hash_evtcl_km_001_11',11);
INSERT INTO "event_cluster_sources" VALUES(25,'evtcl_km_002','news','evtcl_km_002_src0','evtcl_km_002_ev0','财新网：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/0','2018-12-28','hash_evtcl_km_002_0',0);
INSERT INTO "event_cluster_sources" VALUES(26,'evtcl_km_002','news','evtcl_km_002_src1','evtcl_km_002_ev1','证券时报：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/1','2018-12-28','hash_evtcl_km_002_1',1);
INSERT INTO "event_cluster_sources" VALUES(27,'evtcl_km_002','news','evtcl_km_002_src2','evtcl_km_002_ev2','上海证券报：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/2','2018-12-28','hash_evtcl_km_002_2',2);
INSERT INTO "event_cluster_sources" VALUES(28,'evtcl_km_002','news','evtcl_km_002_src3','evtcl_km_002_ev3','第一财经：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/3','2018-12-28','hash_evtcl_km_002_3',3);
INSERT INTO "event_cluster_sources" VALUES(29,'evtcl_km_002','news','evtcl_km_002_src4','evtcl_km_002_ev4','21世纪经济报道：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/4','2018-12-28','hash_evtcl_km_002_4',4);
INSERT INTO "event_cluster_sources" VALUES(30,'evtcl_km_002','news','evtcl_km_002_src5','evtcl_km_002_ev5','中国基金报：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/5','2018-12-28','hash_evtcl_km_002_5',5);
INSERT INTO "event_cluster_sources" VALUES(31,'evtcl_km_002','news','evtcl_km_002_src6','evtcl_km_002_ev6','每日经济新闻：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/6','2018-12-28','hash_evtcl_km_002_6',6);
INSERT INTO "event_cluster_sources" VALUES(32,'evtcl_km_002','news','evtcl_km_002_src7','evtcl_km_002_ev7','新京报：证监会立案调查相关报道','https://demo.truthnet.local/kangmei/evtcl_km_002/7','2018-12-28','hash_evtcl_km_002_7',7);
INSERT INTO "event_cluster_sources" VALUES(33,'evtcl_km_003','news','evtcl_km_003_src0','evtcl_km_003_ev0','财新网：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/0','2019-04-30','hash_evtcl_km_003_0',0);
INSERT INTO "event_cluster_sources" VALUES(34,'evtcl_km_003','news','evtcl_km_003_src1','evtcl_km_003_ev1','证券时报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/1','2019-04-30','hash_evtcl_km_003_1',1);
INSERT INTO "event_cluster_sources" VALUES(35,'evtcl_km_003','news','evtcl_km_003_src2','evtcl_km_003_ev2','上海证券报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/2','2019-04-30','hash_evtcl_km_003_2',2);
INSERT INTO "event_cluster_sources" VALUES(36,'evtcl_km_003','news','evtcl_km_003_src3','evtcl_km_003_ev3','第一财经：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/3','2019-04-30','hash_evtcl_km_003_3',3);
INSERT INTO "event_cluster_sources" VALUES(37,'evtcl_km_003','news','evtcl_km_003_src4','evtcl_km_003_ev4','21世纪经济报道：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/4','2019-04-30','hash_evtcl_km_003_4',4);
INSERT INTO "event_cluster_sources" VALUES(38,'evtcl_km_003','news','evtcl_km_003_src5','evtcl_km_003_ev5','中国基金报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/5','2019-04-30','hash_evtcl_km_003_5',5);
INSERT INTO "event_cluster_sources" VALUES(39,'evtcl_km_003','news','evtcl_km_003_src6','evtcl_km_003_ev6','每日经济新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/6','2019-04-30','hash_evtcl_km_003_6',6);
INSERT INTO "event_cluster_sources" VALUES(40,'evtcl_km_003','news','evtcl_km_003_src7','evtcl_km_003_ev7','新京报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/7','2019-04-30','hash_evtcl_km_003_7',7);
INSERT INTO "event_cluster_sources" VALUES(41,'evtcl_km_003','news','evtcl_km_003_src8','evtcl_km_003_ev8','界面新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/8','2019-04-30','hash_evtcl_km_003_8',8);
INSERT INTO "event_cluster_sources" VALUES(42,'evtcl_km_003','news','evtcl_km_003_src9','evtcl_km_003_ev9','澎湃新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/9','2019-04-30','hash_evtcl_km_003_9',9);
INSERT INTO "event_cluster_sources" VALUES(43,'evtcl_km_003','news','evtcl_km_003_src10','evtcl_km_003_ev10','华尔街见闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/10','2019-04-30','hash_evtcl_km_003_10',10);
INSERT INTO "event_cluster_sources" VALUES(44,'evtcl_km_003','news','evtcl_km_003_src11','evtcl_km_003_ev11','证券市场周刊：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/11','2019-04-30','hash_evtcl_km_003_11',11);
INSERT INTO "event_cluster_sources" VALUES(45,'evtcl_km_003','news','evtcl_km_003_src12','evtcl_km_003_ev12','新浪财经：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/12','2019-04-30','hash_evtcl_km_003_12',12);
INSERT INTO "event_cluster_sources" VALUES(46,'evtcl_km_003','news','evtcl_km_003_src13','evtcl_km_003_ev13','腾讯财经：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/13','2019-04-30','hash_evtcl_km_003_13',13);
INSERT INTO "event_cluster_sources" VALUES(47,'evtcl_km_003','news','evtcl_km_003_src14','evtcl_km_003_ev14','央视财经：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/14','2019-04-30','hash_evtcl_km_003_14',14);
INSERT INTO "event_cluster_sources" VALUES(48,'evtcl_km_003','news','evtcl_km_003_src15','evtcl_km_003_ev15','财新网：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/15','2019-04-30','hash_evtcl_km_003_15',15);
INSERT INTO "event_cluster_sources" VALUES(49,'evtcl_km_003','news','evtcl_km_003_src16','evtcl_km_003_ev16','证券时报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/16','2019-04-30','hash_evtcl_km_003_16',16);
INSERT INTO "event_cluster_sources" VALUES(50,'evtcl_km_003','news','evtcl_km_003_src17','evtcl_km_003_ev17','上海证券报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/17','2019-04-30','hash_evtcl_km_003_17',17);
INSERT INTO "event_cluster_sources" VALUES(51,'evtcl_km_003','news','evtcl_km_003_src18','evtcl_km_003_ev18','第一财经：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/18','2019-04-30','hash_evtcl_km_003_18',18);
INSERT INTO "event_cluster_sources" VALUES(52,'evtcl_km_003','news','evtcl_km_003_src19','evtcl_km_003_ev19','21世纪经济报道：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/19','2019-04-30','hash_evtcl_km_003_19',19);
INSERT INTO "event_cluster_sources" VALUES(53,'evtcl_km_003','news','evtcl_km_003_src20','evtcl_km_003_ev20','中国基金报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/20','2019-04-30','hash_evtcl_km_003_20',20);
INSERT INTO "event_cluster_sources" VALUES(54,'evtcl_km_003','news','evtcl_km_003_src21','evtcl_km_003_ev21','每日经济新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/21','2019-04-30','hash_evtcl_km_003_21',21);
INSERT INTO "event_cluster_sources" VALUES(55,'evtcl_km_003','news','evtcl_km_003_src22','evtcl_km_003_ev22','新京报：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/22','2019-04-30','hash_evtcl_km_003_22',22);
INSERT INTO "event_cluster_sources" VALUES(56,'evtcl_km_003','news','evtcl_km_003_src23','evtcl_km_003_ev23','界面新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/23','2019-04-30','hash_evtcl_km_003_23',23);
INSERT INTO "event_cluster_sources" VALUES(57,'evtcl_km_003','news','evtcl_km_003_src24','evtcl_km_003_ev24','澎湃新闻：299亿货币资金差错更正相关报道','https://demo.truthnet.local/kangmei/evtcl_km_003/24','2019-04-30','hash_evtcl_km_003_24',24);
INSERT INTO "event_cluster_sources" VALUES(58,'evtcl_km_004','news','evtcl_km_004_src0','evtcl_km_004_ev0','财新网：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/0','2019-05-17','hash_evtcl_km_004_0',0);
INSERT INTO "event_cluster_sources" VALUES(59,'evtcl_km_004','news','evtcl_km_004_src1','evtcl_km_004_ev1','证券时报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/1','2019-05-17','hash_evtcl_km_004_1',1);
INSERT INTO "event_cluster_sources" VALUES(60,'evtcl_km_004','news','evtcl_km_004_src2','evtcl_km_004_ev2','上海证券报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/2','2019-05-17','hash_evtcl_km_004_2',2);
INSERT INTO "event_cluster_sources" VALUES(61,'evtcl_km_004','news','evtcl_km_004_src3','evtcl_km_004_ev3','第一财经：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/3','2019-05-17','hash_evtcl_km_004_3',3);
INSERT INTO "event_cluster_sources" VALUES(62,'evtcl_km_004','news','evtcl_km_004_src4','evtcl_km_004_ev4','21世纪经济报道：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/4','2019-05-17','hash_evtcl_km_004_4',4);
INSERT INTO "event_cluster_sources" VALUES(63,'evtcl_km_004','news','evtcl_km_004_src5','evtcl_km_004_ev5','中国基金报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/5','2019-05-17','hash_evtcl_km_004_5',5);
INSERT INTO "event_cluster_sources" VALUES(64,'evtcl_km_004','news','evtcl_km_004_src6','evtcl_km_004_ev6','每日经济新闻：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/6','2019-05-17','hash_evtcl_km_004_6',6);
INSERT INTO "event_cluster_sources" VALUES(65,'evtcl_km_004','news','evtcl_km_004_src7','evtcl_km_004_ev7','新京报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/7','2019-05-17','hash_evtcl_km_004_7',7);
INSERT INTO "event_cluster_sources" VALUES(66,'evtcl_km_004','news','evtcl_km_004_src8','evtcl_km_004_ev8','界面新闻：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/8','2019-05-17','hash_evtcl_km_004_8',8);
INSERT INTO "event_cluster_sources" VALUES(67,'evtcl_km_004','news','evtcl_km_004_src9','evtcl_km_004_ev9','澎湃新闻：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/9','2019-05-17','hash_evtcl_km_004_9',9);
INSERT INTO "event_cluster_sources" VALUES(68,'evtcl_km_004','news','evtcl_km_004_src10','evtcl_km_004_ev10','华尔街见闻：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/10','2019-05-17','hash_evtcl_km_004_10',10);
INSERT INTO "event_cluster_sources" VALUES(69,'evtcl_km_004','news','evtcl_km_004_src11','evtcl_km_004_ev11','证券市场周刊：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/11','2019-05-17','hash_evtcl_km_004_11',11);
INSERT INTO "event_cluster_sources" VALUES(70,'evtcl_km_004','news','evtcl_km_004_src12','evtcl_km_004_ev12','新浪财经：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/12','2019-05-17','hash_evtcl_km_004_12',12);
INSERT INTO "event_cluster_sources" VALUES(71,'evtcl_km_004','news','evtcl_km_004_src13','evtcl_km_004_ev13','腾讯财经：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/13','2019-05-17','hash_evtcl_km_004_13',13);
INSERT INTO "event_cluster_sources" VALUES(72,'evtcl_km_004','news','evtcl_km_004_src14','evtcl_km_004_ev14','央视财经：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/14','2019-05-17','hash_evtcl_km_004_14',14);
INSERT INTO "event_cluster_sources" VALUES(73,'evtcl_km_004','news','evtcl_km_004_src15','evtcl_km_004_ev15','财新网：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/15','2019-05-17','hash_evtcl_km_004_15',15);
INSERT INTO "event_cluster_sources" VALUES(74,'evtcl_km_004','news','evtcl_km_004_src16','evtcl_km_004_ev16','证券时报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/16','2019-05-17','hash_evtcl_km_004_16',16);
INSERT INTO "event_cluster_sources" VALUES(75,'evtcl_km_004','news','evtcl_km_004_src17','evtcl_km_004_ev17','上海证券报：被实施ST风险警示相关报道','https://demo.truthnet.local/kangmei/evtcl_km_004/17','2019-05-17','hash_evtcl_km_004_17',17);
INSERT INTO "event_cluster_sources" VALUES(76,'evtcl_km_005','news','evtcl_km_005_src0','evtcl_km_005_ev0','财新网：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/0','2019-06-01','hash_evtcl_km_005_0',0);
INSERT INTO "event_cluster_sources" VALUES(77,'evtcl_km_005','news','evtcl_km_005_src1','evtcl_km_005_ev1','证券时报：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/1','2019-06-01','hash_evtcl_km_005_1',1);
INSERT INTO "event_cluster_sources" VALUES(78,'evtcl_km_005','news','evtcl_km_005_src2','evtcl_km_005_ev2','上海证券报：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/2','2019-06-01','hash_evtcl_km_005_2',2);
INSERT INTO "event_cluster_sources" VALUES(79,'evtcl_km_005','news','evtcl_km_005_src3','evtcl_km_005_ev3','第一财经：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/3','2019-06-01','hash_evtcl_km_005_3',3);
INSERT INTO "event_cluster_sources" VALUES(80,'evtcl_km_005','news','evtcl_km_005_src4','evtcl_km_005_ev4','21世纪经济报道：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/4','2019-06-01','hash_evtcl_km_005_4',4);
INSERT INTO "event_cluster_sources" VALUES(81,'evtcl_km_005','news','evtcl_km_005_src5','evtcl_km_005_ev5','中国基金报：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/5','2019-06-01','hash_evtcl_km_005_5',5);
INSERT INTO "event_cluster_sources" VALUES(82,'evtcl_km_005','news','evtcl_km_005_src6','evtcl_km_005_ev6','每日经济新闻：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/6','2019-06-01','hash_evtcl_km_005_6',6);
INSERT INTO "event_cluster_sources" VALUES(83,'evtcl_km_005','news','evtcl_km_005_src7','evtcl_km_005_ev7','新京报：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/7','2019-06-01','hash_evtcl_km_005_7',7);
INSERT INTO "event_cluster_sources" VALUES(84,'evtcl_km_005','news','evtcl_km_005_src8','evtcl_km_005_ev8','界面新闻：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/8','2019-06-01','hash_evtcl_km_005_8',8);
INSERT INTO "event_cluster_sources" VALUES(85,'evtcl_km_005','news','evtcl_km_005_src9','evtcl_km_005_ev9','澎湃新闻：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/9','2019-06-01','hash_evtcl_km_005_9',9);
INSERT INTO "event_cluster_sources" VALUES(86,'evtcl_km_005','news','evtcl_km_005_src10','evtcl_km_005_ev10','华尔街见闻：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/10','2019-06-01','hash_evtcl_km_005_10',10);
INSERT INTO "event_cluster_sources" VALUES(87,'evtcl_km_005','news','evtcl_km_005_src11','evtcl_km_005_ev11','证券市场周刊：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/11','2019-06-01','hash_evtcl_km_005_11',11);
INSERT INTO "event_cluster_sources" VALUES(88,'evtcl_km_005','news','evtcl_km_005_src12','evtcl_km_005_ev12','新浪财经：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/12','2019-06-01','hash_evtcl_km_005_12',12);
INSERT INTO "event_cluster_sources" VALUES(89,'evtcl_km_005','news','evtcl_km_005_src13','evtcl_km_005_ev13','腾讯财经：实控人被采取强制措施相关报道','https://demo.truthnet.local/kangmei/evtcl_km_005/13','2019-06-01','hash_evtcl_km_005_13',13);
INSERT INTO "event_cluster_sources" VALUES(90,'evtcl_km_006','news','evtcl_km_006_src0','evtcl_km_006_ev0','财新网：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/0','2019-08-16','hash_evtcl_km_006_0',0);
INSERT INTO "event_cluster_sources" VALUES(91,'evtcl_km_006','news','evtcl_km_006_src1','evtcl_km_006_ev1','证券时报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/1','2019-08-16','hash_evtcl_km_006_1',1);
INSERT INTO "event_cluster_sources" VALUES(92,'evtcl_km_006','news','evtcl_km_006_src2','evtcl_km_006_ev2','上海证券报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/2','2019-08-16','hash_evtcl_km_006_2',2);
INSERT INTO "event_cluster_sources" VALUES(93,'evtcl_km_006','news','evtcl_km_006_src3','evtcl_km_006_ev3','第一财经：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/3','2019-08-16','hash_evtcl_km_006_3',3);
INSERT INTO "event_cluster_sources" VALUES(94,'evtcl_km_006','news','evtcl_km_006_src4','evtcl_km_006_ev4','21世纪经济报道：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/4','2019-08-16','hash_evtcl_km_006_4',4);
INSERT INTO "event_cluster_sources" VALUES(95,'evtcl_km_006','news','evtcl_km_006_src5','evtcl_km_006_ev5','中国基金报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/5','2019-08-16','hash_evtcl_km_006_5',5);
INSERT INTO "event_cluster_sources" VALUES(96,'evtcl_km_006','news','evtcl_km_006_src6','evtcl_km_006_ev6','每日经济新闻：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/6','2019-08-16','hash_evtcl_km_006_6',6);
INSERT INTO "event_cluster_sources" VALUES(97,'evtcl_km_006','news','evtcl_km_006_src7','evtcl_km_006_ev7','新京报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/7','2019-08-16','hash_evtcl_km_006_7',7);
INSERT INTO "event_cluster_sources" VALUES(98,'evtcl_km_006','news','evtcl_km_006_src8','evtcl_km_006_ev8','界面新闻：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/8','2019-08-16','hash_evtcl_km_006_8',8);
INSERT INTO "event_cluster_sources" VALUES(99,'evtcl_km_006','news','evtcl_km_006_src9','evtcl_km_006_ev9','澎湃新闻：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/9','2019-08-16','hash_evtcl_km_006_9',9);
INSERT INTO "event_cluster_sources" VALUES(100,'evtcl_km_006','news','evtcl_km_006_src10','evtcl_km_006_ev10','华尔街见闻：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/10','2019-08-16','hash_evtcl_km_006_10',10);
INSERT INTO "event_cluster_sources" VALUES(101,'evtcl_km_006','news','evtcl_km_006_src11','evtcl_km_006_ev11','证券市场周刊：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/11','2019-08-16','hash_evtcl_km_006_11',11);
INSERT INTO "event_cluster_sources" VALUES(102,'evtcl_km_006','news','evtcl_km_006_src12','evtcl_km_006_ev12','新浪财经：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/12','2019-08-16','hash_evtcl_km_006_12',12);
INSERT INTO "event_cluster_sources" VALUES(103,'evtcl_km_006','news','evtcl_km_006_src13','evtcl_km_006_ev13','腾讯财经：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/13','2019-08-16','hash_evtcl_km_006_13',13);
INSERT INTO "event_cluster_sources" VALUES(104,'evtcl_km_006','news','evtcl_km_006_src14','evtcl_km_006_ev14','央视财经：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/14','2019-08-16','hash_evtcl_km_006_14',14);
INSERT INTO "event_cluster_sources" VALUES(105,'evtcl_km_006','news','evtcl_km_006_src15','evtcl_km_006_ev15','财新网：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/15','2019-08-16','hash_evtcl_km_006_15',15);
INSERT INTO "event_cluster_sources" VALUES(106,'evtcl_km_006','news','evtcl_km_006_src16','evtcl_km_006_ev16','证券时报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/16','2019-08-16','hash_evtcl_km_006_16',16);
INSERT INTO "event_cluster_sources" VALUES(107,'evtcl_km_006','news','evtcl_km_006_src17','evtcl_km_006_ev17','上海证券报：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/17','2019-08-16','hash_evtcl_km_006_17',17);
INSERT INTO "event_cluster_sources" VALUES(108,'evtcl_km_006','news','evtcl_km_006_src18','evtcl_km_006_ev18','第一财经：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/18','2019-08-16','hash_evtcl_km_006_18',18);
INSERT INTO "event_cluster_sources" VALUES(109,'evtcl_km_006','news','evtcl_km_006_src19','evtcl_km_006_ev19','21世纪经济报道：证监会顶格处罚落地相关报道','https://demo.truthnet.local/kangmei/evtcl_km_006/19','2019-08-16','hash_evtcl_km_006_19',19);
CREATE TABLE event_clusters (
	event_cluster_id VARCHAR(64) NOT NULL, 
	entity_id VARCHAR(64) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	topic VARCHAR(256) NOT NULL, 
	summary TEXT NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	event_count INTEGER NOT NULL, 
	sentiment VARCHAR(16) NOT NULL, 
	sentiment_score FLOAT, 
	cluster_method VARCHAR(64) NOT NULL, 
	cluster_version VARCHAR(32) NOT NULL, 
	dataset_version VARCHAR(64) NOT NULL, 
	quality_flags JSON, 
	evidence_ids JSON, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME, 
	PRIMARY KEY (event_cluster_id)
);
INSERT INTO "event_clusters" VALUES('evtcl_km_001','company_600518_SH','600518.SH','存货异常质疑','媒体与做空机构质疑中药存货规模与周转异常，市值两周蒸发超百亿，公司多番澄清未能平息','2018-10-16','2018-10-30',12,'negative',-0.82,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_001_ev0", "evtcl_km_001_ev1", "evtcl_km_001_ev2", "evtcl_km_001_ev3", "evtcl_km_001_ev4", "evtcl_km_001_ev5", "evtcl_km_001_ev6", "evtcl_km_001_ev7", "evtcl_km_001_ev8", "evtcl_km_001_ev9", "evtcl_km_001_ev10", "evtcl_km_001_ev11"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
INSERT INTO "event_clusters" VALUES('evtcl_km_002','company_600518_SH','600518.SH','证监会立案调查','因涉嫌信息披露违法违规，证监会依法对公司立案调查，股价应声跌停','2018-12-28','2018-12-30',8,'negative',-0.9,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_002_ev0", "evtcl_km_002_ev1", "evtcl_km_002_ev2", "evtcl_km_002_ev3", "evtcl_km_002_ev4", "evtcl_km_002_ev5", "evtcl_km_002_ev6", "evtcl_km_002_ev7"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
INSERT INTO "event_clusters" VALUES('evtcl_km_003','company_600518_SH','600518.SH','299亿货币资金差错更正','前期会计差错更正公告承认 2017 年货币资金多记 299.44 亿元，刷新 A 股市场认知','2019-04-30','2019-05-06',25,'negative',-0.97,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_003_ev0", "evtcl_km_003_ev1", "evtcl_km_003_ev2", "evtcl_km_003_ev3", "evtcl_km_003_ev4", "evtcl_km_003_ev5", "evtcl_km_003_ev6", "evtcl_km_003_ev7", "evtcl_km_003_ev8", "evtcl_km_003_ev9", "evtcl_km_003_ev10", "evtcl_km_003_ev11", "evtcl_km_003_ev12", "evtcl_km_003_ev13", "evtcl_km_003_ev14", "evtcl_km_003_ev15", "evtcl_km_003_ev16", "evtcl_km_003_ev17", "evtcl_km_003_ev18", "evtcl_km_003_ev19", "evtcl_km_003_ev20", "evtcl_km_003_ev21", "evtcl_km_003_ev22", "evtcl_km_003_ev23", "evtcl_km_003_ev24"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
INSERT INTO "event_clusters" VALUES('evtcl_km_004','company_600518_SH','600518.SH','被实施ST风险警示','公司股票被实施其他风险警示变更为 ST 康美，复牌后连续多日一字跌停','2019-05-17','2019-05-28',18,'negative',-0.93,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_004_ev0", "evtcl_km_004_ev1", "evtcl_km_004_ev2", "evtcl_km_004_ev3", "evtcl_km_004_ev4", "evtcl_km_004_ev5", "evtcl_km_004_ev6", "evtcl_km_004_ev7", "evtcl_km_004_ev8", "evtcl_km_004_ev9", "evtcl_km_004_ev10", "evtcl_km_004_ev11", "evtcl_km_004_ev12", "evtcl_km_004_ev13", "evtcl_km_004_ev14", "evtcl_km_004_ev15", "evtcl_km_004_ev16", "evtcl_km_004_ev17"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
INSERT INTO "event_clusters" VALUES('evtcl_km_005','company_600518_SH','600518.SH','实控人被采取强制措施','公安机关对实际控制人马兴田夫妇采取强制措施，市场信心彻底崩塌','2019-06-01','2019-06-10',14,'negative',-0.95,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_005_ev0", "evtcl_km_005_ev1", "evtcl_km_005_ev2", "evtcl_km_005_ev3", "evtcl_km_005_ev4", "evtcl_km_005_ev5", "evtcl_km_005_ev6", "evtcl_km_005_ev7", "evtcl_km_005_ev8", "evtcl_km_005_ev9", "evtcl_km_005_ev10", "evtcl_km_005_ev11", "evtcl_km_005_ev12", "evtcl_km_005_ev13"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
INSERT INTO "event_clusters" VALUES('evtcl_km_006','company_600518_SH','600518.SH','证监会顶格处罚落地','证监会对公司顶格处罚 60 万元，对马兴田等主要责任人罚款并终身证券市场禁入','2019-08-16','2019-08-25',20,'negative',-0.88,'embedding_cluster','v1','demo_v1',NULL,'["evtcl_km_006_ev0", "evtcl_km_006_ev1", "evtcl_km_006_ev2", "evtcl_km_006_ev3", "evtcl_km_006_ev4", "evtcl_km_006_ev5", "evtcl_km_006_ev6", "evtcl_km_006_ev7", "evtcl_km_006_ev8", "evtcl_km_006_ev9", "evtcl_km_006_ev10", "evtcl_km_006_ev11", "evtcl_km_006_ev12", "evtcl_km_006_ev13", "evtcl_km_006_ev14", "evtcl_km_006_ev15", "evtcl_km_006_ev16", "evtcl_km_006_ev17", "evtcl_km_006_ev18", "evtcl_km_006_ev19"]','2026-08-25 16:48:53','2026-08-25 16:48:53');
CREATE TABLE evidence_refs (
	evidence_id VARCHAR(64) NOT NULL, 
	source_type VARCHAR(32) NOT NULL, 
	source_record_id VARCHAR(256) NOT NULL, 
	company_code VARCHAR(32), 
	field_path VARCHAR(256), 
	period VARCHAR(10), 
	value VARCHAR(256), 
	unit VARCHAR(16), 
	statement_scope VARCHAR(32), 
	source_title VARCHAR(512), 
	source_uri VARCHAR(1024), 
	source_excerpt TEXT, 
	retrieval_score FLOAT, 
	dataset_version VARCHAR(64) NOT NULL, 
	retrieved_at DATETIME NOT NULL, 
	turn_id VARCHAR(64), 
	trace_id VARCHAR(64), 
	module VARCHAR(32), 
	source_table VARCHAR(64), 
	PRIMARY KEY (evidence_id)
);
INSERT INTO "evidence_refs" VALUES('ev_fin_0038ac10d70f6a66','financial_statement','600518.SH|2015-12-31','600518.SH','net_profit_excl_min_int_inc','2015-12-31','165000.0','元','parent_company','现金流–利润背离 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_4f1b7701bc56c057','financial_statement','600518.SH|2015-12-31','600518.SH','net_cash_flows_oper_act','2015-12-31','42000.0','元','parent_company','现金流–利润背离 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','cash_flow');
INSERT INTO "evidence_refs" VALUES('ev_fin_8fb7dedfd478ce33','financial_statement','600518.SH|2016-12-31','600518.SH','net_profit_excl_min_int_inc','2016-12-31','195000.0','元','parent_company','现金流–利润背离 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_38fe58970823bd75','financial_statement','600518.SH|2016-12-31','600518.SH','net_cash_flows_oper_act','2016-12-31','38000.0','元','parent_company','现金流–利润背离 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','cash_flow');
INSERT INTO "evidence_refs" VALUES('ev_fin_d3d410de1bc92a7f','financial_statement','600518.SH|2017-12-31','600518.SH','net_profit_excl_min_int_inc','2017-12-31','235000.0','元','parent_company','现金流–利润背离 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_22156210f15f5c71','financial_statement','600518.SH|2017-12-31','600518.SH','net_cash_flows_oper_act','2017-12-31','-185000.0','元','parent_company','现金流–利润背离 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','cash_flow');
INSERT INTO "evidence_refs" VALUES('ev_fin_35ec81196b291553','financial_statement','600518.SH|2018-12-31','600518.SH','net_profit_excl_min_int_inc','2018-12-31','-195000.0','元','parent_company','现金流–利润背离 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_12b5ddd24283a7b2','financial_statement','600518.SH|2018-12-31','600518.SH','net_cash_flows_oper_act','2018-12-31','-320000.0','元','parent_company','现金流–利润背离 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','cash_flow');
INSERT INTO "evidence_refs" VALUES('ev_fin_a0805bca2cc1c88d','financial_statement','600518.SH|2015-12-31','600518.SH','monetary_cap','2015-12-31','1580000.0','元','parent_company','存贷双高 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_1e0797e4edf2dd0e','financial_statement','600518.SH|2015-12-31','600518.SH','st_borrow','2015-12-31','460000.0','元','parent_company','存贷双高 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_e5079b06e11e0636','financial_statement','600518.SH|2015-12-31','600518.SH','lt_borrow','2015-12-31','180000.0','元','parent_company','存贷双高 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_b062b738f321df41','financial_statement','600518.SH|2015-12-31','600518.SH','tot_assets','2015-12-31','3810000.0','元','parent_company','存贷双高 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_d6a0bdb069599c9c','financial_statement','600518.SH|2015-12-31','600518.SH','less_fin_exp','2015-12-31','72000.0','元','parent_company','存贷双高 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_da77c89233a6525f','financial_statement','600518.SH|2016-12-31','600518.SH','monetary_cap','2016-12-31','2730000.0','元','parent_company','存贷双高 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_c5cc97c894916a0a','financial_statement','600518.SH|2016-12-31','600518.SH','st_borrow','2016-12-31','820000.0','元','parent_company','存贷双高 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_f89a517bf75a55b7','financial_statement','600518.SH|2016-12-31','600518.SH','lt_borrow','2016-12-31','240000.0','元','parent_company','存贷双高 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_ab0c186286a8e8fc','financial_statement','600518.SH|2016-12-31','600518.SH','tot_assets','2016-12-31','5480000.0','元','parent_company','存贷双高 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_f1547d94b1873ff7','financial_statement','600518.SH|2016-12-31','600518.SH','less_fin_exp','2016-12-31','86000.0','元','parent_company','存贷双高 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_947f39fd528118bf','financial_statement','600518.SH|2017-12-31','600518.SH','monetary_cap','2017-12-31','3420000.0','元','parent_company','存贷双高 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_8e02bb70f5ccc05f','financial_statement','600518.SH|2017-12-31','600518.SH','st_borrow','2017-12-31','1130000.0','元','parent_company','存贷双高 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_363362a52c3dc854','financial_statement','600518.SH|2017-12-31','600518.SH','lt_borrow','2017-12-31','350000.0','元','parent_company','存贷双高 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_f52d13d9d7e9d98b','financial_statement','600518.SH|2017-12-31','600518.SH','tot_assets','2017-12-31','6870000.0','元','parent_company','存贷双高 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_336d435f61d20911','financial_statement','600518.SH|2017-12-31','600518.SH','less_fin_exp','2017-12-31','105000.0','元','parent_company','存贷双高 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_391849078053c21f','financial_statement','600518.SH|2018-12-31','600518.SH','monetary_cap','2018-12-31','180000.0','元','parent_company','存贷双高 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_bf5bff705ac21306','financial_statement','600518.SH|2018-12-31','600518.SH','st_borrow','2018-12-31','1350000.0','元','parent_company','存贷双高 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_a40fc5f539c0ce09','financial_statement','600518.SH|2018-12-31','600518.SH','lt_borrow','2018-12-31','420000.0','元','parent_company','存贷双高 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_c3ec416715b65cff','financial_statement','600518.SH|2018-12-31','600518.SH','tot_assets','2018-12-31','2650000.0','元','parent_company','存贷双高 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_527265ff7a238e2a','financial_statement','600518.SH|2018-12-31','600518.SH','less_fin_exp','2018-12-31','138000.0','元','parent_company','存贷双高 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_02599521cdbed155','financial_statement','600518.SH|2015-12-31','600518.SH','oper_rev','2015-12-31','1800000.0','元','parent_company','毛利率/费用率异常 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_cb87c26679d370cf','financial_statement','600518.SH|2015-12-31','600518.SH','less_oper_cost','2015-12-31','1310000.0','元','parent_company','毛利率/费用率异常 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_76eee8e02ca574b1','financial_statement','600518.SH|2015-12-31','600518.SH','less_selling_dist_exp','2015-12-31','125000.0','元','parent_company','毛利率/费用率异常 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_3c745ad607cf9e50','financial_statement','600518.SH|2015-12-31','600518.SH','less_gerl_admin_exp','2015-12-31','98000.0','元','parent_company','毛利率/费用率异常 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_a155539ae3d92cde','financial_statement','600518.SH|2016-12-31','600518.SH','oper_rev','2016-12-31','2160000.0','元','parent_company','毛利率/费用率异常 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_8dbd9d630dbd2f79','financial_statement','600518.SH|2016-12-31','600518.SH','less_oper_cost','2016-12-31','1570000.0','元','parent_company','毛利率/费用率异常 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_f614f09c260d40e1','financial_statement','600518.SH|2016-12-31','600518.SH','less_selling_dist_exp','2016-12-31','156000.0','元','parent_company','毛利率/费用率异常 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_58ab6a18a2751d61','financial_statement','600518.SH|2016-12-31','600518.SH','less_gerl_admin_exp','2016-12-31','118000.0','元','parent_company','毛利率/费用率异常 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_633671310de9326b','financial_statement','600518.SH|2017-12-31','600518.SH','oper_rev','2017-12-31','2640000.0','元','parent_company','毛利率/费用率异常 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_464910c137146f73','financial_statement','600518.SH|2017-12-31','600518.SH','less_oper_cost','2017-12-31','1930000.0','元','parent_company','毛利率/费用率异常 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_7c2b0d31dc5b83b1','financial_statement','600518.SH|2017-12-31','600518.SH','less_selling_dist_exp','2017-12-31','188000.0','元','parent_company','毛利率/费用率异常 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_1ee5c03a14ef00bd','financial_statement','600518.SH|2017-12-31','600518.SH','less_gerl_admin_exp','2017-12-31','142000.0','元','parent_company','毛利率/费用率异常 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_da76edc055c14e3d','financial_statement','600518.SH|2018-12-31','600518.SH','oper_rev','2018-12-31','1820000.0','元','parent_company','毛利率/费用率异常 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_114c390fed1c8e82','financial_statement','600518.SH|2018-12-31','600518.SH','less_oper_cost','2018-12-31','1560000.0','元','parent_company','毛利率/费用率异常 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_7c9122e027c7ebd2','financial_statement','600518.SH|2018-12-31','600518.SH','less_selling_dist_exp','2018-12-31','165000.0','元','parent_company','毛利率/费用率异常 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_2eade9b9db42792f','financial_statement','600518.SH|2018-12-31','600518.SH','less_gerl_admin_exp','2018-12-31','135000.0','元','parent_company','毛利率/费用率异常 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','income_statement');
INSERT INTO "evidence_refs" VALUES('ev_fin_eef0d1fc6fdc5eb9','financial_statement','600518.SH|2015-12-31','600518.SH','oth_rcv','2015-12-31','18000.0','元','parent_company','其他应收款与关联占用风险 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_7c9155b34c2715fc','financial_statement','600518.SH|2015-12-31','600518.SH','acct_rcv','2015-12-31','280000.0','元','parent_company','其他应收款与关联占用风险 · 2015-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_5c7285aa3b47cc06','financial_statement','600518.SH|2016-12-31','600518.SH','oth_rcv','2016-12-31','22000.0','元','parent_company','其他应收款与关联占用风险 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_7f30a6fca9c3eb10','financial_statement','600518.SH|2016-12-31','600518.SH','acct_rcv','2016-12-31','310000.0','元','parent_company','其他应收款与关联占用风险 · 2016-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_472863b55e039fdd','financial_statement','600518.SH|2017-12-31','600518.SH','oth_rcv','2017-12-31','38000.0','元','parent_company','其他应收款与关联占用风险 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_0421e59f11b15dbd','financial_statement','600518.SH|2017-12-31','600518.SH','acct_rcv','2017-12-31','430000.0','元','parent_company','其他应收款与关联占用风险 · 2017-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_7b37cf1e2d7a81e6','financial_statement','600518.SH|2018-12-31','600518.SH','oth_rcv','2018-12-31','22000.0','元','parent_company','其他应收款与关联占用风险 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_fin_608ce6366b4e24f5','financial_statement','600518.SH|2018-12-31','600518.SH','acct_rcv','2018-12-31','380000.0','元','parent_company','其他应收款与关联占用风险 · 2018-12-31 · 母公司报表',NULL,NULL,NULL,'mock-v12','2026-08-25 06:49:11','9ec12fe1-377e-400c-8c22-eb752be222c4','9ec12fe1-377e-400c-8c22-eb752be222c4','finance','balance_sheet');
INSERT INTO "evidence_refs" VALUES('ev_eq_79a4e639407c4494','neo4j_relationship','nx_ent_kangmei_industrial_600518','600518.SH','ownership_pct',NULL,'30.10',NULL,'ownership_record','康美实业→康美药业 持股 30.10',NULL,NULL,NULL,'networkx-lite','2026-08-25 06:49:46.226352+00:00',NULL,'ee9fb8be-bc83-4d98-a8cf-adedd60af5ff','equity','neo4j:OWNS');
INSERT INTO "evidence_refs" VALUES('ev_eq_fff2ca256f7b3f9a','neo4j_relationship','nx_ent_ma_xingtian_ent_kangmei_industrial','600518.SH','ownership_pct',NULL,'99.70',NULL,'ownership_record','马兴田→康美实业 持股 99.70',NULL,NULL,NULL,'networkx-lite','2026-08-25 06:49:46.226352+00:00',NULL,'ee9fb8be-bc83-4d98-a8cf-adedd60af5ff','equity','neo4j:OWNS');
INSERT INTO "evidence_refs" VALUES('ev_ann_f6abc2d94599ce67','announcement','kmfy_ann_20190816_penalty','600518.SH',NULL,'2019-08-16',NULL,NULL,'parent_company',NULL,NULL,NULL,NULL,'mock-v12','2026-08-25 08:54:01','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','events','announcements');
INSERT INTO "evidence_refs" VALUES('ev_ann_cbb62baa15523fc2','announcement','kmfy_ann_20190517_st','600518.SH',NULL,'2019-05-17',NULL,NULL,'parent_company',NULL,NULL,NULL,NULL,'mock-v12','2026-08-25 08:54:01','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','events','announcements');
INSERT INTO "evidence_refs" VALUES('ev_ann_5ced0a4708734b28','announcement','kmfy_ann_20190430_restate','600518.SH',NULL,'2019-04-30',NULL,NULL,'parent_company',NULL,NULL,NULL,NULL,'mock-v12','2026-08-25 08:54:01','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','events','announcements');
INSERT INTO "evidence_refs" VALUES('ev_ann_1b565d50286b6bf9','announcement','kmfy_ann_20181229_csrc','600518.SH',NULL,'2018-12-29',NULL,NULL,'parent_company',NULL,NULL,NULL,NULL,'mock-v12','2026-08-25 08:54:01','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','9a41c432-56a4-49d1-9bb6-f407aa0a60dd','events','announcements');
CREATE TABLE income_statement (
	wind_code VARCHAR(32) NOT NULL, 
	report_period VARCHAR(10) NOT NULL, 
	statement_type VARCHAR(32) NOT NULL, 
	ann_dt VARCHAR(10), 
	oper_rev FLOAT, 
	tot_oper_rev FLOAT, 
	less_oper_cost FLOAT, 
	less_selling_dist_exp FLOAT, 
	less_gerl_admin_exp FLOAT, 
	less_fin_exp FLOAT, 
	oper_profit FLOAT, 
	tot_profit FLOAT, 
	net_profit_excl_min_int_inc FLOAT, 
	net_profit_after_ded_nr_lp FLOAT, 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_is_report UNIQUE (wind_code, report_period, statement_type, ann_dt, revision_no)
);
INSERT INTO "income_statement" VALUES('600518.SH','2015-12-31','408006000','2016-04-25',1800000.0,1806000.0,1310000.0,125000.0,98000.0,72000.0,200000.0,195000.0,165000.0,163000.0,1,'kmfy_is_2015-12-31','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.931853','2026-08-25 08:44:45.931855','null',NULL);
INSERT INTO "income_statement" VALUES('600518.SH','2016-12-31','408006000','2017-04-28',2160000.0,2164000.0,1570000.0,156000.0,118000.0,86000.0,232000.0,228000.0,195000.0,188000.0,2,'kmfy_is_2016-12-31','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.931932','2026-08-25 08:44:45.931933','null',NULL);
INSERT INTO "income_statement" VALUES('600518.SH','2017-12-31','408006000','2018-04-26',2640000.0,2648000.0,1930000.0,188000.0,142000.0,105000.0,280000.0,275000.0,235000.0,228000.0,3,'kmfy_is_2017-12-31','scripts/load_kangmei_fixture.py',3,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.931964','2026-08-25 08:44:45.931964','null',NULL);
INSERT INTO "income_statement" VALUES('600518.SH','2018-12-31','408006000','2019-04-30',1820000.0,1824000.0,1560000.0,165000.0,135000.0,138000.0,-176000.0,-192000.0,-195000.0,-198000.0,4,'kmfy_is_2018-12-31','scripts/load_kangmei_fixture.py',4,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.931990','2026-08-25 08:44:45.931990','null',NULL);
CREATE TABLE industry_benchmarks (
	benchmark_id VARCHAR(64) NOT NULL, 
	industry_l1 VARCHAR(64) NOT NULL, 
	industry_l2 VARCHAR(64), 
	metric_id VARCHAR(32) NOT NULL, 
	rule_id VARCHAR(16) NOT NULL, 
	period VARCHAR(10) NOT NULL, 
	statement_scope VARCHAR(32) NOT NULL, 
	company_type SMALLINT, 
	sample_count INTEGER NOT NULL, 
	mean_value FLOAT, 
	std_value FLOAT, 
	min_value FLOAT, 
	p05 FLOAT, 
	p25 FLOAT, 
	p50 FLOAT, 
	p75 FLOAT, 
	p95 FLOAT, 
	max_value FLOAT, 
	dataset_version VARCHAR(64) NOT NULL, 
	rule_set_version VARCHAR(32) NOT NULL, 
	calculated_at DATETIME NOT NULL, 
	PRIMARY KEY (benchmark_id), 
	CONSTRAINT uq_industry_benchmark_key UNIQUE (industry_l1, metric_id, period, statement_scope, dataset_version)
);
CREATE TABLE rating_changes (
	rating_change_id VARCHAR(64) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	quarter VARCHAR(8) NOT NULL, 
	institution VARCHAR(256) NOT NULL, 
	previous_rating VARCHAR(32), 
	current_rating VARCHAR(32) NOT NULL, 
	direction VARCHAR(16) NOT NULL, 
	report_id VARCHAR(128), 
	published_at VARCHAR(10), 
	confidence FLOAT, 
	evidence_id VARCHAR(64), 
	dataset_version VARCHAR(64) NOT NULL, 
	PRIMARY KEY (rating_change_id), 
	CONSTRAINT uq_rating_change_key UNIQUE (wind_code, quarter, institution, report_id)
);
CREATE TABLE report_jobs (
	report_id VARCHAR(64) NOT NULL, 
	session_id VARCHAR(64), 
	company_code VARCHAR(32), 
	status VARCHAR(16) NOT NULL, 
	progress INTEGER NOT NULL, 
	idempotency_key VARCHAR(128), 
	request_payload JSON, 
	file_path VARCHAR(512), 
	file_sha256 VARCHAR(64), 
	retry_count INTEGER NOT NULL, 
	error_code VARCHAR(64), 
	error_message TEXT, 
	trace_id VARCHAR(64), 
	created_at DATETIME NOT NULL, 
	started_at DATETIME, 
	completed_at DATETIME, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (report_id), 
	UNIQUE (idempotency_key)
);
CREATE TABLE research_reports (
	report_id VARCHAR(128) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	sec_code VARCHAR(32), 
	exchange_code VARCHAR(16), 
	sec_name VARCHAR(128), 
	org_name VARCHAR(256), 
	title VARCHAR(512) NOT NULL, 
	publish_date VARCHAR(10), 
	abstract TEXT, 
	rating_org VARCHAR(32), 
	rating_change VARCHAR(16), 
	industry_l1 VARCHAR(64), 
	sw_indu_code VARCHAR(32), 
	source_uri VARCHAR(1024), 
	content_hash VARCHAR(128), 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	UNIQUE (report_id)
);
INSERT INTO "research_reports" VALUES('kmfy_rpt_20190506_citics','600518.SH','600518','XSHG','康美药业','中信证券研究部','康美药业（600518.SH）会计差错更正点评：差错更正暴露内控缺陷，下调至卖出评级','2019-05-06','康美药业公告前期会计差错更正，涉及货币资金调减299亿元。公司2017年末货币资金由341.5亿元更正为42.5亿元，差异巨大。下调至卖出评级，目标价下调至3.0元。','卖出','down','医药生物','370101','https://research.citics.com/report/600518_20190506',NULL,1,'kmfy_rpt_20190506_citics','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.938920','2026-08-25 08:44:45.938922','null',NULL);
INSERT INTO "research_reports" VALUES('kmfy_rpt_20190820_gtja','600518.SH','600518','XSHG','康美药业','国泰君安证券研究所','康美药业（600518.SH）行政处罚点评：造假金额创A股纪录，退市风险加大','2019-08-20','证监会拟对康美药业处以60万元罚款并市场禁入。公司2016-2018年累计虚增营业收入约275亿元，虚增货币资金约887亿元，虚增固定资产、在建工程约36亿元。维持卖出评级。','卖出','maintain','医药生物','370101','https://research.gtja.com/report/600518_20190820',NULL,2,'kmfy_rpt_20190820_gtja','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.939001','2026-08-25 08:44:45.939002','null',NULL);
CREATE TABLE risk_assessments (
	id INTEGER NOT NULL, 
	assessment_id VARCHAR(64) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	overall_score FLOAT, 
	financial_score FLOAT, 
	ownership_score FLOAT, 
	sentiment_score FLOAT, 
	level VARCHAR(16) NOT NULL, 
	risk_factors JSON, 
	rule_version VARCHAR(32) NOT NULL, 
	dataset_version VARCHAR(64) NOT NULL, 
	assessed_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (assessment_id)
);
CREATE TABLE rule_definitions (
	rule_id VARCHAR(64) NOT NULL, 
	rule_name VARCHAR(256) NOT NULL, 
	category VARCHAR(64) NOT NULL, 
	description TEXT NOT NULL, 
	formula TEXT, 
	threshold JSON, 
	severity VARCHAR(16) NOT NULL, 
	version VARCHAR(32) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (rule_id)
);
CREATE TABLE rule_evaluations (
	id INTEGER NOT NULL, 
	rule_id VARCHAR(64) NOT NULL, 
	wind_code VARCHAR(32) NOT NULL, 
	report_period VARCHAR(10) NOT NULL, 
	result VARCHAR(16), 
	score FLOAT, 
	detail JSON, 
	evaluated_at DATETIME NOT NULL, 
	rule_version VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(rule_id) REFERENCES rule_definitions (rule_id) ON DELETE CASCADE
);
CREATE TABLE top_shareholders (
	wind_code VARCHAR(32) NOT NULL, 
	ann_dt VARCHAR(10), 
	s_holder_enddate VARCHAR(10), 
	s_holder_name VARCHAR(256) NOT NULL, 
	s_holder_aname VARCHAR(256), 
	s_holder_pct NUMERIC(10, 4), 
	s_holder_quantity NUMERIC(20, 2), 
	s_holder_holdercategory VARCHAR(64), 
	s_holder_sequence INTEGER, 
	report_period VARCHAR(10), 
	holder_entity_id VARCHAR(64), 
	entity_match_confidence FLOAT, 
	id INTEGER NOT NULL, 
	source_record_id VARCHAR(256), 
	source_file VARCHAR(512), 
	source_row INTEGER, 
	source_type VARCHAR(64), 
	dataset_version VARCHAR(64), 
	revision_no INTEGER NOT NULL, 
	is_latest BOOLEAN NOT NULL, 
	ingested_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	quality_flags JSON, 
	checksum VARCHAR(128), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_top_shareholders_source_record_id UNIQUE (source_record_id)
);
INSERT INTO "top_shareholders" VALUES('600518.SH','2019-04-30','2018-12-31','康美实业投资控股有限公司','康美实业',31.91,1585000000,'境内一般法人',1,'2018-12-31','company_km_sy',1.0,1,'kmfy_tsh_01','scripts/load_kangmei_fixture.py',1,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.935912','2026-08-25 08:44:45.935914','null',NULL);
INSERT INTO "top_shareholders" VALUES('600518.SH','2019-04-30','2018-12-31','广东粤财信托有限公司','粤财信托',4.52,224500000,'信托计划',2,'2018-12-31','company_yc_xt',0.95,2,'kmfy_tsh_02','scripts/load_kangmei_fixture.py',2,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.935989','2026-08-25 08:44:45.935990','null',NULL);
INSERT INTO "top_shareholders" VALUES('600518.SH','2019-04-30','2018-12-31','中国证券金融股份有限公司','证金公司',3.77,187200000,'国有法人',3,'2018-12-31','company_zj_gs',1.0,3,'kmfy_tsh_03','scripts/load_kangmei_fixture.py',3,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.936019','2026-08-25 08:44:45.936019','null',NULL);
INSERT INTO "top_shareholders" VALUES('600518.SH','2019-04-30','2018-12-31','许冬瑾',NULL,2.48,123100000,'境内自然人',4,'2018-12-31',NULL,NULL,4,'kmfy_tsh_04','scripts/load_kangmei_fixture.py',4,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.936052','2026-08-25 08:44:45.936052','null',NULL);
INSERT INTO "top_shareholders" VALUES('600518.SH','2019-04-30','2018-12-31','普宁市金信典当行有限公司','金信典当',2.05,101800000,'境内一般法人',5,'2018-12-31','company_jx_dd',0.85,5,'kmfy_tsh_05','scripts/load_kangmei_fixture.py',5,'fixture','kangmei-fixture-v1',1,1,'2026-08-25 08:44:45.936078','2026-08-25 08:44:45.936078','null',NULL);
CREATE UNIQUE INDEX ix_companies_wind_code ON companies (wind_code);
CREATE INDEX ix_balance_sheet_wind_code ON balance_sheet (wind_code);
CREATE INDEX ix_balance_sheet_report_period ON balance_sheet (report_period);
CREATE INDEX ix_income_statement_wind_code ON income_statement (wind_code);
CREATE INDEX ix_income_statement_report_period ON income_statement (report_period);
CREATE INDEX ix_cash_flow_report_period ON cash_flow (report_period);
CREATE INDEX ix_cash_flow_wind_code ON cash_flow (wind_code);
CREATE INDEX ix_top_shareholders_holder_entity_id ON top_shareholders (holder_entity_id);
CREATE INDEX ix_top_shareholders_wind_code ON top_shareholders (wind_code);
CREATE INDEX ix_announcements_wind_code ON announcements (wind_code);
CREATE INDEX ix_research_reports_wind_code ON research_reports (wind_code);
CREATE INDEX ix_rule_definitions_category ON rule_definitions (category);
CREATE INDEX ix_evidence_refs_turn_id ON evidence_refs (turn_id);
CREATE INDEX ix_evidence_refs_trace_id ON evidence_refs (trace_id);
CREATE INDEX ix_claims_trace_id ON claims (trace_id);
CREATE INDEX ix_claims_turn_id ON claims (turn_id);
CREATE INDEX ix_event_clusters_wind_code ON event_clusters (wind_code);
CREATE INDEX ix_risk_assessments_wind_code ON risk_assessments (wind_code);
CREATE INDEX ix_industry_benchmarks_period ON industry_benchmarks (period);
CREATE INDEX ix_industry_benchmarks_industry_l1 ON industry_benchmarks (industry_l1);
CREATE INDEX ix_industry_benchmarks_metric_id ON industry_benchmarks (metric_id);
CREATE INDEX ix_rating_changes_wind_code ON rating_changes (wind_code);
CREATE INDEX ix_rating_changes_quarter ON rating_changes (quarter);
CREATE INDEX ix_analysis_runs_trace_id ON analysis_runs (trace_id);
CREATE INDEX ix_report_jobs_session_id ON report_jobs (session_id);
CREATE INDEX ix_report_jobs_company_code ON report_jobs (company_code);
CREATE INDEX ix_report_jobs_status ON report_jobs (status);
CREATE INDEX ix_conversation_turns_session_id ON conversation_turns (session_id);
CREATE INDEX ix_rule_evaluations_wind_code ON rule_evaluations (wind_code);
CREATE INDEX ix_rule_evaluations_rule_id ON rule_evaluations (rule_id);
CREATE INDEX ix_claim_evidence_links_evidence_id ON claim_evidence_links (evidence_id);
CREATE INDEX ix_claim_evidence_links_claim_id ON claim_evidence_links (claim_id);
CREATE INDEX ix_event_cluster_sources_event_cluster_id ON event_cluster_sources (event_cluster_id);
CREATE INDEX ix_event_cluster_sources_evidence_id ON event_cluster_sources (evidence_id);
COMMIT;