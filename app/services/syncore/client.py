"""SynCore HRMS client (class-based)."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.http import post_json
from app.services.syncore.codec import decode, encode, get_code

logger = logging.getLogger(__name__)


class SynCoreClient:
    def __init__(self, config: Dict[str, str]) -> None:
        self.config = {
            "HR_CODE": config.get("HR_CODE", ""),
            "API_BASE": (config.get("API_BASE", "") or "").rstrip("/"),
            "DEFAULT_USER_ID": config.get("DEFAULT_USER_ID", ""),
            "DEFAULT_SIGNED_ARRAY": config.get("DEFAULT_SIGNED_ARRAY", ""),
            "DATE_FMT": config.get("DATE_FMT", "%m/%d/%Y"),
        }

    def build_user_payload(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "hrcode": self.config["HR_CODE"],
            "user_id": user_id or self.config["DEFAULT_USER_ID"],
            "project_status": 1,
            "signed_array": signed_array or self.config["DEFAULT_SIGNED_ARRAY"],
        }
        if extra_fields:
            payload.update(extra_fields)
        return payload

    def post_request(self, endpoint: str, payload: Dict[str, Any], log: bool = False) -> Dict:
        url = f"{self.config['API_BASE']}{endpoint}"
        encoded_payload = encode(payload)
        try:
            resp = post_json(url, encoded_payload, timeout=30)
            if resp.status_code == 200:
                data = decode(resp.json())
                if log:
                    logger.info("SynCore API response: %s", data)
                return data
            logger.error(
                "SynCore API request failed: status=%s, endpoint=%s",
                resp.status_code,
                endpoint,
            )
            return {"error": f"Failed with status {resp.status_code}"}
        except Exception as exc:
            logger.error("SynCore API request exception: %s", exc)
            return {"error": f"Request failed: {exc}"}

    def parse_date(self, date_str: Optional[str]):
        if not date_str or date_str == "None":
            return None
        try:
            return datetime.strptime(str(date_str), self.config["DATE_FMT"]).date()
        except (ValueError, TypeError):
            return None

    def get_all_employees(self) -> List[Dict]:
        endpoint = "/user/get_users"
        payload = self.build_user_payload()
        logger.info("Fetching all employees from SynCore HRMS")
        data = self.post_request(endpoint, payload)
        if "error" in data:
            logger.error("Failed to fetch employees: %s", data["error"])
            return []
        employees = []
        for user in data.get("response_data", []):
            user["signed_array"] = get_code(user)
            employees.append(user)
        logger.info("Successfully fetched %d employees from SynCore", len(employees))
        return employees

    def get_today_log_status(
        self, user_id: Optional[str] = None, signed_array: Optional[str] = None
    ) -> List[Dict]:
        data = self.post_request(
            "/attendance/total_logs_detail",
            self.build_user_payload(user_id, signed_array),
        )
        if "error" in data:
            return []
        return data.get("response_data", [])

    def get_emp_projects(
        self, user_id: Optional[str] = None, signed_array: Optional[str] = None
    ) -> List[Dict]:
        data = self.post_request(
            "/project/get_emp_projects",
            self.build_user_payload(user_id, signed_array),
        )
        if not isinstance(data, dict) or "error" in data:
            return []
        response_data = data.get("response_data", [])
        return response_data if isinstance(response_data, list) else []

    def get_user_mail_setting(
        self, user_id: Optional[str] = None, signed_array: Optional[str] = None
    ) -> Dict:
        data = self.post_request(
            "/setting/get_user_mail_setting",
            self.build_user_payload(user_id, signed_array),
        )
        if not isinstance(data, dict) or "error" in data:
            return {}
        response_data = data.get("response_data", {})
        if isinstance(response_data, list) and response_data:
            response_data = response_data[0]
        return response_data if isinstance(response_data, dict) else {}

    def get_attendance(
        self,
        start_date: str = "",
        end_date: str = "",
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
    ) -> List[Dict]:
        payload = self.build_user_payload(
            user_id,
            signed_array,
            {"start_date": start_date, "end_date": end_date},
        )
        data = self.post_request("/attendance/show_attendance", payload)
        if not isinstance(data, dict) or "error" in data:
            return []
        response_data = data.get("response_data", [])
        return response_data if isinstance(response_data, list) else []

    def get_employee_leaves(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        resolved_user_id = user_id or self.config["DEFAULT_USER_ID"]
        data = self.post_request(
            "/leavemanager/get_user_leave_record",
            self.build_user_payload(user_id, signed_array),
        )
        if not isinstance(data, dict) or "error" in data:
            return []
        leaves = data.get("response_data", [])
        if not isinstance(leaves, list):
            leaves = [leaves] if leaves else []
        start = self.parse_date(start_date)
        end = self.parse_date(end_date)
        result = []
        for leave in leaves:
            applied_date = self.parse_date(leave.get("applied_date"))
            if str(leave.get("user_id")) != str(resolved_user_id):
                continue
            if not applied_date:
                continue
            if start and applied_date < start:
                continue
            if end and applied_date > end:
                continue
            result.append(leave)
        return result

    def get_webex_token(
        self, user_id: Optional[str] = None, signed_array: Optional[str] = None
    ) -> Dict:
        data = self.post_request(
            "/user/get_user_spark_id",
            self.build_user_payload(user_id, signed_array),
        )
        if not isinstance(data, dict):
            return {"error": "Invalid response format"}
        if "error" in data:
            return {"error": data["error"]}
        result = data.get("response_data", data)
        if data.get("status") == "Success":
            return {"token": result}
        return {"error": data.get("message", "Error in getting the token")}

    def get_holiday_and_leave_calendar(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        start = self.parse_date(start_date)
        end = self.parse_date(end_date)
        if not start or not end:
            raise ValueError("start_date and end_date must be valid MM/DD/YYYY dates")
        data = self.post_request(
            "/leavemanager/get_holiday_leave_records",
            self.build_user_payload(user_id, signed_array),
        )
        if not isinstance(data, dict):
            return {"holidays": [], "leaves": {}}
        if "error" in data:
            return {"holidays": [], "leaves": {}, "error": data["error"]}
        records = data.get("response_data", [])
        if not isinstance(records, list):
            records = [records] if records else []
        date_fmt = self.config["DATE_FMT"]
        holidays = []
        leaves_by_date: dict = defaultdict(list)
        for record in records:
            record_date = self.parse_date(record.get("date"))
            if not record_date or record_date < start or record_date > end:
                continue
            name = record.get("name", "")
            key = record_date.strftime(date_fmt)
            if name.startswith("Leave:") or name.startswith("Half Day Leave:"):
                leaves_by_date[key].append(name)
            else:
                holidays.append({"name": name, "date": key})
        return {"holidays": holidays, "leaves": dict(leaves_by_date)}

    def get_project_modules(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict]:
        data = self.post_request(
            "/project/get_modules",
            self.build_user_payload(user_id, signed_array, {"project_id": project_id}),
        )
        if not isinstance(data, dict) or "error" in data:
            return []
        response_data = data.get("response_data", [])
        if not isinstance(response_data, list):
            response_data = [response_data] if response_data else []
        return response_data

    def get_project_activities(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict]:
        data = self.post_request(
            "/project/get_activities",
            self.build_user_payload(user_id, signed_array, {"project_id": project_id}),
        )
        if not isinstance(data, dict) or "error" in data:
            return []
        response_data = data.get("response_data", [])
        if not isinstance(response_data, list):
            response_data = [response_data] if response_data else []
        return response_data

    def get_emp_project_log(
        self,
        start_date: str = "",
        end_date: str = "",
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        project_id: int = 0,
        module_id: int = 0,
        activity_id: int = 0,
    ) -> List[Dict]:
        payload = {
            "hrcode": self.config["HR_CODE"],
            "project_id": project_id,
            "emp_id": user_id or self.config["DEFAULT_USER_ID"],
            "module_id": module_id,
            "activity_id": activity_id,
            "start_date": start_date,
            "end_date": end_date,
            "groupby": "none",
            "sortby": "ASC",
            "signed_array": signed_array or self.config["DEFAULT_SIGNED_ARRAY"],
        }
        data = self.post_request("/project/get_emp_project_log", payload)
        if not isinstance(data, dict) or "error" in data:
            return []
        response_data = data.get("response_data", [])
        if not isinstance(response_data, list):
            response_data = [response_data] if response_data else []
        return response_data

    def login(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        override_comment: str = "",
    ) -> Dict:
        data = self.post_request(
            "/attendance/fill_attendance",
            self.build_user_payload(
                user_id, signed_array, {"override_comment": override_comment}
            ),
        )
        if not isinstance(data, dict):
            return {"error": "Invalid response format"}
        if "error" in data:
            return data
        result = data.get("response_data", {})
        if isinstance(result, dict):
            result["message"] = data.get("message", "")
            return result
        return {"message": data.get("message", ""), "response_data": result}

    def logout(
        self,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
        override_comment: str = "",
    ) -> Dict:
        return self.login(user_id, signed_array, override_comment)

    def fill_work_log(
        self,
        project_id,
        module_id,
        activity_id,
        work_desc: str,
        hour_clocked,
        user_id: Optional[str] = None,
        signed_array: Optional[str] = None,
    ) -> Dict:
        extra_fields = {
            "project_id1": project_id,
            "module_id1": module_id,
            "activity_id1": activity_id,
            "work_desc1": work_desc,
            "hour_clocked1": hour_clocked,
            "work_quantified11": "",
            "work_quantified21": "",
            "log_date1": "",
            "send_mail1": "false",
            "project_id2": 0,
            "module_id2": 0,
            "activity_id2": 0,
            "work_quantified12": "",
            "work_quantified22": "",
            "log_date2": "",
            "send_mail2": "false",
        }
        data = self.post_request(
            "/project/fill_daily_log",
            self.build_user_payload(user_id, signed_array, extra_fields),
        )
        if not isinstance(data, dict):
            return {"error": "Invalid response format"}
        if "error" in data:
            return {"error": data["error"]}
        if data.get("status") == "Success":
            return {
                "token": data.get("response_data", data),
                "message": data.get("message", "Work log submitted successfully."),
            }
        return {"error": data.get("message", "Failed to submit work log.")}