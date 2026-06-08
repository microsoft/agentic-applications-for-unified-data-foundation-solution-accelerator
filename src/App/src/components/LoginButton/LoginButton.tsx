import React, { useCallback } from "react";
import {
  Avatar,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  MenuDivider,
  Button,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { Person24Regular, SignOut24Regular } from "@fluentui/react-icons";
import { useAppSelector } from "../../store/hooks";

const useStyles = makeStyles({
  userButton: {
    minWidth: "auto",
    paddingLeft: tokens.spacingHorizontalXS,
    paddingRight: tokens.spacingHorizontalXS,
  },
  userInfo: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    maxWidth: "260px",
    minWidth: 0,
  },
  userName: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: "13px",
    maxWidth: "100%",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  userEmail: {
    fontSize: "11px",
    color: tokens.colorNeutralForeground2,
    maxWidth: "100%",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
});

const getUserInitials = (fullName: string | undefined): string => {
  if (!fullName) return "U";
  const cleanName = fullName.replace(/\s*\([^)]*\)/g, "").trim();
  if (!cleanName) return "U";
  const parts = cleanName.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return cleanName.charAt(0).toUpperCase();
};

const LoginButton: React.FC = () => {
  const styles = useStyles();
  const userName = useAppSelector((state) => state.app.userName);
  const userEmail = useAppSelector((state) => state.app.userEmail);
  const isAuthenticated = useAppSelector((state) => state.app.isAuthenticated);

  const handleLogout = useCallback(() => {
    localStorage.removeItem("userId");
    sessionStorage.removeItem("accessToken");
    window.location.href =
      "/.auth/logout?post_logout_redirect_uri=" +
      encodeURIComponent(window.location.origin);
  }, []);

  if (!isAuthenticated) {
    return (
      <Avatar icon={<Person24Regular />} size={28} color="neutral" />
    );
  }

  const displayName = userName || "User";

  return (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <Button
          appearance="subtle"
          className={styles.userButton}
          title={userName ? `Signed in as ${userName}` : "User menu"}
          aria-label={userName ? `User menu for ${userName}` : "User menu"}
          icon={
            <Avatar
              name={displayName}
              initials={getUserInitials(userName)}
              icon={!userName ? <Person24Regular /> : undefined}
              size={28}
              color={userName ? "colorful" : "neutral"}
              style={{ fontWeight: "bold" }}
            />
          }
        />
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <MenuItem icon={<Person24Regular />} disabled>
            <div className={styles.userInfo}>
              <span className={styles.userName} title={userName || "User"}>
                {userName || "User"}
              </span>
              {userEmail && (
                <span className={styles.userEmail} title={userEmail}>
                  {userEmail}
                </span>
              )}
            </div>
          </MenuItem>
          <MenuDivider />
          <MenuItem icon={<SignOut24Regular />} onClick={handleLogout}>
            Sign out
          </MenuItem>
        </MenuList>
      </MenuPopover>
    </Menu>
  );
};

export default LoginButton;
